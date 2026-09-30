"""JWT signing for worker → Odoo result delivery.

The worker delivers the result of every job to Odoo. Since Wave 3 (review
finding P1-3) that is an HTTP POST to ``/invoice_agent/result`` — the result
used to be published to the ``invoice.result`` AMQP queue and drained by a
thread inside Odoo, and **only the transport changed**. Odoo must not trust
the caller blindly either way: the endpoint is ``auth='none'`` and reachable
by anything on the internal network. So the worker wraps the payload in a
short-lived HS256 JWT signed with the **same shared secret** that already
protects the request direction (``INVOICE_AI_JWT_SECRET``, mirrored on the
Odoo side as ``invoice_agent.jwt_secret``). The signature *is* the
authentication.

Request body: ``{"token": "<jwt>"}`` where the JWT claims carry the result:

    {iss: "invoice-ai", aud: "odoo.invoice-agent", iat, exp,
     sub: "extract.done",
     result: {job_uuid, move_id, status, parsed_output, usage, model}}

The audience ``odoo.invoice-agent`` is the mirror of the request direction
(worker-facing tokens use aud ``invoice-ai``). Odoo verifies signature /
expiry / audience before applying any field; a rejected token is answered
``401`` — a secret mismatch is a configuration fault, so the worker would
dead-letter rather than retry it forever.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import settings

_logger = logging.getLogger(__name__)

RESULT_ISSUER = "invoice-ai"
RESULT_AUDIENCE = "odoo.invoice-agent"
RESULT_SUBJECT = "extract.done"
# The token is minted immediately before each delivery (``_deliver_result``
# signs at send time, not at job start), so 5 minutes is far more headroom
# than the HTTP round-trip needs — it only has to outlive clock skew between
# the two containers plus the request itself.
RESULT_TTL_SECONDS = 300


class ResultSigningError(Exception):
    """Raised when a result payload cannot be signed/verified."""


def sign_result(payload: dict[str, Any], secret: str | None = None) -> str:
    """Wrap a result payload in a signed JWT.

    :param payload: the result dict (job_uuid, move_id, status, ...).
    :param secret: override for tests; defaults to ``settings.jwt_secret``.
    :raises ResultSigningError: when no secret is configured.
    """
    import jwt

    secret = secret if secret is not None else settings.jwt_secret
    if not secret:
        raise ResultSigningError(
            "INVOICE_AI_JWT_SECRET is not configured — cannot sign results",
        )
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": RESULT_ISSUER,
            "aud": RESULT_AUDIENCE,
            "sub": RESULT_SUBJECT,
            "iat": now,
            "exp": now + timedelta(seconds=RESULT_TTL_SECONDS),
            "result": payload,
        },
        secret,
        algorithm="HS256",
    )


def verify_result(token: str, secret: str | None = None) -> dict[str, Any]:
    """Verify and return the ``result`` claims of a signed result token.

    :raises ResultSigningError: missing secret, bad signature, expiry,
        wrong audience/subject, or a missing ``result`` claim.
    """
    import jwt
    from jwt.exceptions import InvalidTokenError

    secret = secret if secret is not None else settings.jwt_secret
    if not secret:
        raise ResultSigningError(
            "no JWT secret configured — cannot verify signed results",
        )
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=RESULT_AUDIENCE,
            leeway=10,
            issuer=RESULT_ISSUER,
        )
    except InvalidTokenError as exc:
        raise ResultSigningError(f"invalid result token: {exc}") from exc
    if claims.get("sub") != RESULT_SUBJECT:
        raise ResultSigningError("result token has the wrong subject")
    result = claims.get("result")
    if not isinstance(result, dict):
        raise ResultSigningError("result token carries no result payload")
    return result
