"""Async worker — consumes ``invoice.extract`` jobs and applies them.

Run with ``python -m app.consumer`` (the compose ``worker`` service command).
Flow per job (QoS prefetch=1, manual ack):

1. Connect robustly (``aio_pika.connect_robust``) and declare the topology
   (``app/amqp.py``) — re-declared on every reconnect so a broker reset heals
   itself.
2. Consume one ``extract.request`` message. Body contract
   (docs/queue-contract.md): ``{"move_id", "attachment_id", "attempt",
   "job_uuid", "ocr_text"}``.
3. Deliver ``extract.started`` to Odoo so the UI flips to *extracting* live.
4. Run Claude extraction (``ClaudeService.extract`` — AsyncAnthropic, never
   a blocking SDK call on the loop).
5. Deliver the JWT-signed result (``app/result_signing.py``) to Odoo, then ack
   the original.

**Result delivery is HTTP, not AMQP.** Results used to be published on
``invoice.agent``/``extract.done`` to the ``invoice.result`` queue, which Odoo
drained with a daemon thread in every process. Odoo now exposes
``POST /invoice_agent/result`` (review finding P1-3 / Wave 3) and
``app/odoo_result.py`` posts the same signed ``{"token": ...}`` envelope
there. Only the *result* direction moved: ``invoice.extract`` is still AMQP,
because that is the direction Odoo initiates and the queue gives it the
durability, ordering and retry-ladder behaviour it needs.

Failure routing (v0.9 — retry ladder + dead-letter queue, see app/retry.py):

* ``ClaudeRateLimitError`` / ``ClaudeUpstreamError`` (429, 5xx, connection):
  publish on the DLX exchange to the retry tier selected by the attempt
  counter (``retry.5s`` -> ``retry.30s`` -> ``retry.5m``), then ack the
  original. The tier's ``x-message-ttl`` is the backoff; expiry re-publishes
  to ``invoice.agent``/``extract.request``. Exhausting the ladder
  dead-letters instead.
* ``ResultDeliveryError`` — routed the same way, using its own ``transient``
  flag: a transport error, HTTP 5xx, 429, or 409 (Odoo has no bill for this
  result *yet*) rides the ladder; 400 or 401 dead-letters immediately,
  because retrying cannot fix a malformed envelope or a shared secret the two
  sides disagree about.
* ``BadRequestError`` / ``ExtractionValidationError`` / malformed body:
  publish on the DLX to ``extract.dead`` AND deliver a signed
  ``status:"failed"`` result to Odoo, then ack the original. The dead queue
  owns the message; the signed failure lets Odoo mark the originating outbox
  job dead and flag the move. Retrying never fixes a bad schema — these must
  never burn another Anthropic call.
* Unknown failure without an attempt counter: discard (ack, no republish).
* ``x-delivery-limit: 3`` on the queue is the safety net: a worker crash
  mid-job (unacked) redelivers at most 3 times before the broker itself
  dead-letters. A poison PDF can never loop forever.

``connect_robust`` reattaches after broker restarts with built-in retry and
redeclares the topology on each reconnect, so the worker survives RabbitMQ
outages mid-batch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage

from .amqp import (
    DLX_EXCHANGE,
    QUEUE_EXTRACT,
    declare_topology,
)
from .claude import ClaudeService
from .errors import BadRequestError, ClaudeRateLimitError, ClaudeUpstreamError
from .llm_cache import cache_get, cache_set
from .metrics import (
    CLAUDE_API_DURATION,
    WORKER_JOB_DURATION,
    WORKER_JOBS_TOTAL,
    Timer,
    record_claude_tokens,
)
from .odoo_result import OdooResultClient, ResultDeliveryError
from .result_signing import ResultSigningError, sign_result
from .retrieve import retrieve_vendor_context
from .retry import (
    DEAD_ROUTING_KEY,
    RetryDecision,
    RetryExhausted,
    attempt_from_body,
    classify_failure,
    tier_for_attempt,
)
from .schemas import InvoiceExtraction
from .validate import validate_extraction

_logger = logging.getLogger(__name__)

PREFETCH_COUNT = 1

# How the worker hands a signed envelope to Odoo. A callable seam (rather than
# a hard call to ``OdooResultClient``) so tests can record deliveries without
# a live Odoo, exactly like the ``sign`` seam.
DeliverFn = Callable[[dict[str, Any]], Awaitable[None]]


class WorkerError(Exception):
    """Raised when a job cannot be processed at all (malformed body)."""


def _parse_body(message: AbstractIncomingMessage) -> dict:
    """Decode + validate the job body.

    :raises WorkerError: invalid JSON or a non-object body — the caller
        treats this as a poison message.
    """
    try:
        payload = json.loads(message.body or b"{}")
    except (TypeError, ValueError) as exc:
        raise WorkerError(f"invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkerError(f"body is not a JSON object: {type(payload).__name__}")
    return payload


async def _deliver_to_odoo(envelope: dict[str, Any]) -> None:
    """Default delivery: POST the signed envelope to Odoo's result webhook."""
    await OdooResultClient().post_result(envelope)


class InvoiceConsumer:
    """aio-pika consumer for the ``invoice.extract`` queue.

    Owns one robust connection + channel. Injectable ``claude``, ``sign`` and
    ``deliver`` seams so tests exercise the full routing logic on a fake
    broker and a recording transport without touching Anthropic or Odoo.
    """

    def __init__(
        self,
        claude: ClaudeService | None = None,
        sign: Callable[[dict[str, Any]], str] = sign_result,
        deliver: DeliverFn = _deliver_to_odoo,
    ):
        self._claude = claude or ClaudeService()
        self._sign = sign
        self._deliver = deliver

    async def run(self, amqp_url: str) -> None:
        """Connect robustly and consume until cancelled."""
        connection = await aio_pika.connect_robust(amqp_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=PREFETCH_COUNT)

        # (Re)declare the full topology on every connect — see amqp.py.
        # declare_topology declares invoice.extract WITH its DLX arguments
        # and binds it on extract.request. Do NOT re-declare it here with a
        # bare (argument-less) declare — RabbitMQ treats an empty argument
        # table as inequivalent to the queue's existing DLX args and closes
        # the channel with 406 PRECONDITION_FAILED.
        await declare_topology(channel)

        queue = await channel.get_queue(QUEUE_EXTRACT)
        # Only the DLX is still needed: results no longer go to a topic
        # exchange, so the ``invoice.agent`` exchange is not fetched here.
        dlx = await channel.get_exchange(DLX_EXCHANGE)

        _logger.info(
            "invoice-ai worker: consuming %s (prefetch=%d)",
            QUEUE_EXTRACT,
            PREFETCH_COUNT,
        )
        try:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    await self._handle_message(message, dlx)
        finally:
            await connection.close()
            _logger.info("invoice-ai worker: connection closed")

    async def _handle_message(
        self,
        message: AbstractIncomingMessage,
        dlx: AbstractExchange,
    ) -> None:
        async with message.process(requeue=False):
            try:
                body = _parse_body(message)
            except WorkerError as exc:
                await self._dead_letter(dlx, message, exc)
                return

            attempt = attempt_from_body(body)
            job_uuid = body.get("job_uuid") or ""
            move_id = body.get("move_id")
            ocr_text = body.get("ocr_text") or ""

            # Track overall job duration from consume to result delivery.
            job_start = time.monotonic()

            if not job_uuid or not move_id:
                await self._dead_letter(
                    dlx,
                    message,
                    WorkerError("job body missing job_uuid/move_id"),
                )
                return

            # Live UI state: best-effort. Failing to tell Odoo "extracting" must
            # never cost the extraction itself, so this is logged and swallowed
            # — the result delivery at the end is what must succeed.
            try:
                await self._deliver_status(job_uuid, move_id, "extracting")
            except Exception:
                _logger.warning(
                    "invoice-ai worker: could not deliver extracting status "
                    "for move_id=%s (continuing with the extraction)",
                    move_id,
                    exc_info=True,
                )

            try:
                # --- LLM cache lookup ---
                # Check Redis for a cached extraction before calling Claude.
                # On hit, skip the API call entirely (saves tokens + latency).
                cached = cache_get(ocr_text, model=self._claude._cfg.anthropic_model)
                if cached and "result" in cached:
                    result = cached["result"]
                    _logger.info(
                        "invoice-ai worker: cache hit for move_id=%s",
                        move_id,
                    )
                else:
                    # Track Claude API latency in the worker
                    model_name = self._claude._cfg.anthropic_model
                    with Timer(CLAUDE_API_DURATION, model=model_name):
                        result = await self._claude.extract(text=ocr_text)
                    # Record token consumption
                    record_claude_tokens(
                        model=result["model"],
                        usage=result["usage"],
                    )
                    # Store in cache for future requests with same OCR text
                    try:
                        cache_set(
                            ocr_text,
                            result,
                            model=result.get("model", ""),
                        )
                    except Exception:
                        _logger.exception(
                            "invoice-ai worker: failed to cache result for move_id=%s",
                            move_id,
                        )
            except (ClaudeRateLimitError, ClaudeUpstreamError, BadRequestError) as exc:
                decision = classify_failure(exc, attempt)
                await self._route_failure(dlx, message, decision)
                return
            except Exception as exc:
                # Unknown/validation errors — be conservative, dead-letter.
                decision = classify_failure(exc, attempt)
                await self._route_failure(dlx, message, decision)
                return

            # Cache writes store `parsed` as JSON (pydantic models are
            # serialized in app/llm_cache.py). Re-validate it back to the
            # model so the delivery + validation paths below can call
            # `model_dump()` / attribute access unchanged. Only dict input
            # (the JSON form from cache) is re-validated — model instances
            # and test doubles are left untouched.
            parsed = result["parsed"]
            if isinstance(parsed, dict):
                parsed = InvoiceExtraction.model_validate(parsed)
            result["parsed"] = parsed

            # --- Phase 2: RAG validation (retrieve + validate) ---
            # Best-effort: if retrieval or validation fails, the extraction
            # result is still delivered — Odoo can surface it without the
            # validation envelope.
            #
            # The ``rag_enabled`` flag is a kill switch stored as
            # ``ir.config_parameter``. When False, the worker skips
            # retrieval + validation entirely, reverting to v0.9
            # extraction-only behaviour.
            validation_verdict = None
            validation_usage = None
            rag_enabled = body.get("rag_enabled", True)
            try:
                partner_id = body.get("partner_id")
                if partner_id and rag_enabled:
                    extraction: InvoiceExtraction = result["parsed"]
                    # Retrieve vendor context (hybrid vector + ref + VAT)
                    vendor_context = await retrieve_vendor_context(
                        partner_id=int(partner_id),
                        ocr_text=ocr_text,
                        extracted_ref=body.get("ref") or "",
                        extracted_vat=extraction.vendor_vat or "",
                        extracted_vendor_name=extraction.vendor_name or "",
                    )
                    # Validate extraction against vendor history
                    val_result = await validate_extraction(
                        extraction=extraction,
                        vendor_context=vendor_context,
                        ocr_text=ocr_text,
                    )
                    validation_verdict = val_result["verdict"].model_dump(
                        mode="json",
                    )
                    validation_usage = val_result["usage"]
                    _logger.info(
                        "invoice-ai worker: validation done for move_id=%s "
                        "account=%s confidence=%.2f cache_read=%s",
                        move_id,
                        validation_verdict.get("account_id"),
                        validation_verdict.get("account_confidence", 0),
                        (
                            validation_usage.get("cache_read_input_tokens")
                            if validation_usage
                            else None
                        ),
                    )
            except Exception:
                _logger.exception(
                    "invoice-ai worker: RAG validation failed for "
                    "move_id=%s — extraction result stands without validation",
                    move_id,
                )

            payload = {
                "job_uuid": job_uuid,
                "move_id": move_id,
                "status": "done",
                "parsed_output": result["parsed"].model_dump(mode="json"),
                "usage": result["usage"],
                "model": result["model"],
                "attempt": attempt or 1,
            }
            # Attach validation envelope when available
            if validation_verdict is not None:
                payload["validation"] = validation_verdict
                payload["validation_usage"] = validation_usage
            try:
                await self._deliver_result(payload)
            except ResultSigningError as exc:
                # Config error (missing INVOICE_AI_JWT_SECRET) — retrying can
                # never fix a missing secret. Dead-letter the job so it is
                # visible on the taskboard instead of looping forever.
                await self._dead_letter(dlx, message, exc)
                return
            except ResultDeliveryError as exc:
                # Odoo's own status code decides: transient (transport, 5xx,
                # 429, 409) rides the retry ladder; permanent (400, 401)
                # dead-letters immediately.
                decision = self._classify_delivery_failure(exc, attempt)
                await self._route_failure(dlx, message, decision)
                return
            except Exception as exc:
                # Any other delivery failure: route through the retry/dead logic.
                decision = classify_failure(exc, attempt)
                await self._route_failure(dlx, message, decision)
                return

            # Record successful job metrics
            job_elapsed = time.monotonic() - job_start
            WORKER_JOBS_TOTAL.labels(status="done").inc()
            WORKER_JOB_DURATION.observe(job_elapsed)
            _logger.info(
                "invoice-ai worker: job %s move_id=%s done model=%s validation=%s duration=%.1fs",
                job_uuid,
                move_id,
                result["model"],
                "yes" if validation_verdict else "no",
                job_elapsed,
            )

    async def _deliver_status(
        self,
        job_uuid: str,
        move_id: int,
        status: str,
        **extra: Any,
    ) -> None:
        """Deliver a lifecycle status (``extracting``) to Odoo, signed.

        The status message goes through the same signed envelope as a result,
        because Odoo's route verifies the signature before it trusts anything
        in the body — including a status. The signing function pins the
        ``sub`` claim; the ``status`` field is what Odoo branches on.
        """
        payload = {
            "job_uuid": job_uuid,
            "move_id": int(move_id),
            "status": status,
        }
        payload.update(extra)
        token = self._sign(payload)
        await self._deliver({"token": token})

    async def _deliver_result(self, payload: dict) -> None:
        """Sign a result payload and POST it to Odoo."""
        token = self._sign(payload)
        await self._deliver({"token": token})

    @staticmethod
    def _classify_delivery_failure(
        exc: ResultDeliveryError,
        attempt: int | None,
    ) -> RetryDecision:
        """Map a ``ResultDeliveryError`` onto the retry ladder.

        Kept here rather than in ``app/retry.py`` on purpose: ``retry.py`` is
        deliberately free of any transport or SDK import so it unit-tests with
        no dependencies, and ``ResultDeliveryError`` lives with httpx. The
        classification itself is the same shape as ``classify_failure``'s.
        """
        if attempt is None:
            return RetryDecision(
                route="discard",
                reason=f"unclassifiable delivery failure (no attempt): {exc}",
            )
        if not exc.transient:
            return RetryDecision(
                route="dead",
                attempt=attempt,
                reason=(
                    f"permanent result delivery failure "
                    f"(HTTP {exc.status_code}): {exc}"
                ),
            )
        try:
            tier = tier_for_attempt(attempt)
        except RetryExhausted:
            return RetryDecision(
                route="dead",
                attempt=attempt,
                reason=(
                    "transient result delivery failure exhausted the retry "
                    f"ladder: {exc}"
                ),
            )
        return RetryDecision(
            route="retry",
            tier=tier,
            attempt=attempt,
            reason=f"transient result delivery failure: {exc}",
        )

    async def _route_failure(
        self,
        dlx: AbstractExchange,
        message: AbstractIncomingMessage,
        decision: RetryDecision,
    ) -> None:
        """Route a failed job to the retry ladder or the dead queue.

        The original message is acked by ``message.process(requeue=False)``
        regardless — routing happens through the DLX publish, never by
        requeueing, so the broker cannot redeliver it in a tight loop.
        """
        if decision.is_retry:
            await self._publish_to_dlx(
                dlx,
                routing_key=f"retry.{decision.tier}",
                body=message.body,
                headers=dict(message.headers or {}),
            )
            _logger.warning(
                "invoice-ai worker: %s -> retry tier %s (attempt %s)",
                decision.reason,
                decision.tier,
                decision.attempt,
            )
        elif decision.is_dead:
            await self._dead_letter(dlx, message, decision.reason)
        else:
            WORKER_JOBS_TOTAL.labels(status="failed").inc()
            _logger.warning(
                "invoice-ai worker: discarding unclassifiable message: %s",
                decision.reason,
            )

    async def _dead_letter(
        self,
        dlx: AbstractExchange,
        message: AbstractIncomingMessage,
        reason: Any,
        notify_odoo: bool = True,
    ) -> None:
        """Publish to the poison queue and let the original ack.

        ``reason`` is surfaced as the ``x-death-reason`` header on the dead
        message so the dead queue (and the management UI) shows WHY the job
        was poisoned. When the body carries a correlatable ``job_uuid``, a
        signed ``status:"failed"`` result is ALSO delivered to Odoo so it can
        mark the originating outbox job dead and flag the move — the
        dead-letter is visible in the Odoo taskboard, not just the management
        UI.
        """
        headers = dict(message.headers or {})
        headers["x-death-reason"] = str(reason)[:2000]
        await self._publish_to_dlx(
            dlx,
            routing_key=DEAD_ROUTING_KEY,
            body=message.body,
            headers=headers,
        )
        if notify_odoo:
            try:
                body = _parse_body(message)
                job_uuid = body.get("job_uuid") or ""
                move_id = body.get("move_id")
                if job_uuid and move_id:
                    failed_payload = {
                        "job_uuid": job_uuid,
                        "move_id": int(move_id),
                        "status": "failed",
                        "error": str(reason)[:2000],
                    }
                    await self._deliver_result(failed_payload)
            except Exception:
                _logger.exception(
                    "invoice-ai worker: could not deliver failed result for "
                    "dead-lettered job",
                )
        WORKER_JOBS_TOTAL.labels(status="dead-lettered").inc()
        _logger.warning("invoice-ai worker: dead-lettered job: %s", reason)

    async def _publish_to_dlx(
        self,
        dlx: AbstractExchange,
        routing_key: str,
        body: bytes,
        headers: dict | None = None,
    ) -> None:
        await dlx.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=headers or {},
            ),
            routing_key=routing_key,
        )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from .amqp import build_amqp_url

    consumer = InvoiceConsumer()
    await consumer.run(build_amqp_url())


if __name__ == "__main__":
    asyncio.run(main())
