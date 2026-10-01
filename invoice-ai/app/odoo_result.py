"""HTTP delivery of worker results to Odoo (worker -> Odoo direction).

Replaces the AMQP ``invoice.result`` publish (review finding P1-3 / Wave 3).
Odoo used to run a daemon thread per process to drain that queue; it now
exposes ``POST /invoice_agent/result`` and this client posts the signed JWT
envelope there instead.

The envelope shape is unchanged from the AMQP era — ``{"token": "<jwt>"}`` —
so ``app/result_signing.py`` and the Odoo-side verification are untouched.
Only the transport moved.

Failure classification. Odoo's status codes are meaningful here, so they are
mapped explicitly rather than collapsed into "delivery failed":

* **transient** — a transport error, HTTP 5xx, 429, or 409. 409 means Odoo
  accepted the signature but has no bill for this result *yet*; Odoo releases
  its idempotency claim in that case precisely so a retry can succeed, so
  retrying is the correct response.
* **permanent** — 400 (malformed envelope) or 401 (the two sides disagree
  about the shared secret). Retrying can never fix either, and a 401 must be
  surfaced loudly rather than hammered.
"""

from __future__ import annotations

import logging

import httpx

from .config import settings

_logger = logging.getLogger(__name__)

# Odoo's "I have no bill for this result yet" (the claim was released).
_ODOO_NO_MATCHING_BILL = 409
# Upstream rate limit.
_HTTP_TOO_MANY_REQUESTS = 429


class ResultDeliveryError(Exception):
    """Raised when a result could not be delivered to Odoo.

    ``transient`` tells the consumer whether the retry ladder can help;
    ``status_code`` is ``None`` for a transport failure.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.transient = transient


def _is_transient_status(status_code: int) -> bool:
    """True when the same request could succeed later."""
    return (
        status_code >= 500
        or status_code == _HTTP_TOO_MANY_REQUESTS
        or status_code == _ODOO_NO_MATCHING_BILL
    )


class OdooResultClient:
    """Posts signed results to Odoo's ``/invoice_agent/result`` webhook."""

    def __init__(
        self,
        base_url: str | None = None,
        path: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.odoo_base_url).rstrip("/")
        self._path = path or settings.odoo_result_path
        self._timeout = timeout or settings.odoo_result_timeout_seconds

    @property
    def url(self) -> str:
        """The full webhook URL this client posts to."""
        return f"{self._base_url}{self._path}"

    async def post_result(self, envelope: dict) -> None:
        """POST one ``{"token": ...}`` envelope to Odoo.

        A fresh ``AsyncClient`` per call is deliberate: the worker's consumer
        loop is long-lived but result deliveries are rare (one per completed
        job), so the connection-setup cost is irrelevant next to the Claude
        call that precedes it, and it avoids adding client lifecycle
        management to the consumer for no measured gain.

        :raises ResultDeliveryError: transport failure or any non-2xx response,
            with ``transient`` set when a retry could plausibly succeed.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self.url, json=envelope)
        except httpx.HTTPError as exc:
            raise ResultDeliveryError(
                f"Odoo result webhook unreachable at {self.url}: {exc}",
                transient=True,
            ) from exc

        if response.status_code >= 400:
            detail = (response.text or "").strip()[:300]
            transient = _is_transient_status(response.status_code)
            raise ResultDeliveryError(
                f"Odoo rejected the result (HTTP {response.status_code}): {detail}",
                status_code=response.status_code,
                transient=transient,
            )

        _logger.info(
            "odoo result delivered (HTTP %s): %s",
            response.status_code,
            (response.text or "").strip()[:200],
        )
