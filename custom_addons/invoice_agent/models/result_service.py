"""Result intake for the ``invoice-ai`` worker (Wave 3 / P1-3).

The worker used to publish its signed result to the ``invoice.result`` AMQP
queue, and Odoo ran a daemon thread in every process to drain it. That is now
an **HTTP webhook**: the worker POSTs the same signed JWT to
``/invoice_agent/result`` (``controllers/main.py``) and this service verifies
and applies it *inside a normal request*.

What moving it behind a request removes — and why each removal matters:

* **No daemon thread.** Nothing to start from ``post_load``, so the
  ``"post_load"`` manifest hook and the ``post_load()`` function are gone,
  and with them the "the thread died, restart it" lifetime problem.
* **No hand-built environment.** A request already has a real ``request.env``
  with the right user, company and context, so ``with_company`` and record
  rules behave normally instead of being reconstructed from a
  ``registry.cursor()`` plus ``api.Environment(cr, SUPERUSER_ID, {})``.
* **No per-process broker connection.** ``post_load`` ran in every process, so
  an 8-worker deployment held eight AMQP connections (plus eight io-loops) for
  one logical consumer. An HTTP route holds none between calls.
* **No database guessing.** ``_resolve_db_name`` had to infer the database
  from an env var, ``odoo.conf``, or "whichever registry happens to be
  loaded". The HTTP dispatcher has already selected the database by the time
  the route runs.

The security properties are unchanged, deliberately:

* the HS256 signature is verified against the same
  ``invoice.llm.service._jwt_secret()`` single owner the HTTP direction uses,
  so the worker's signing secret and this verifier cannot drift;
* the audience/issuer/subject claims are still pinned (they are the contract
  with ``invoice-ai/app/result_signing.py``);
* ``claim_job_uuid`` is the *same* ``INSERT ... ON CONFLICT DO NOTHING``
  ledger, unchanged, which is what makes at-least-once delivery a no-op on
  redelivery.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Result JWT claims — must match ``invoice-ai/app/result_signing.py``. A
# mismatch is a contract break, not a bug on one side, so it is pinned here
# and there and nowhere else.
RESULT_AUDIENCE = "odoo.invoice-agent"
RESULT_ISSUER = "invoice-ai"
RESULT_SUBJECT = "extract.done"
# Clock-skew allowance on ``iat``/``exp``.
RESULT_LEEWAY_SECONDS = 10


class InvoiceAgentResultService(models.AbstractModel):
    """Verifies and applies a signed result posted by the ``invoice-ai`` worker.

    Every method is ``@api.model``: the service is stateless and is always
    called as ``self.env["invoice.agent.result.service"]``.
    """

    _name = "invoice.agent.result.service"
    _description = "Verify and apply a signed invoice-ai worker result"

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    @api.model
    def verify_token(self, token):
        """Verify a signed result token and return its ``result`` claims.

        A rejection is a ``None`` return, never a raise: a forged or expired
        result must not surface as a server error (which a caller might
        retry), and it must never reach the apply path.

        :return: the ``result`` dict, or ``None`` when the token is absent,
            unsigned, signed with the wrong secret, expired, or addressed to
            a different audience/issuer/subject.
        """
        import jwt
        from jwt.exceptions import InvalidTokenError

        if not token:
            _logger.warning("invoice_agent: result carried no token")
            return None
        # Resolve the shared secret through the same single owner the HTTP
        # direction uses (INVOICE_AI_JWT_SECRET env first, then the
        # invoice_agent.jwt_secret ir.config_parameter). A missing secret is a
        # rejection, not a traceback.
        try:
            secret = self.env["invoice.llm.service"]._jwt_secret()
        except Exception:
            secret = None
        if not secret:
            _logger.warning(
                "invoice_agent: no JWT secret configured — rejecting result",
            )
            return None
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=RESULT_AUDIENCE,
                issuer=RESULT_ISSUER,
                leeway=RESULT_LEEWAY_SECONDS,
            )
        except InvalidTokenError as exc:
            _logger.warning("invoice_agent: rejected result token: %s", exc)
            return None
        if claims.get("sub") != RESULT_SUBJECT:
            _logger.warning("invoice_agent: result token has the wrong subject")
            return None
        result = claims.get("result")
        if not isinstance(result, dict):
            _logger.warning("invoice_agent: result token carries no payload")
            return None
        return result

    # ------------------------------------------------------------------
    # Idempotency ledger
    # ------------------------------------------------------------------
    @api.model
    def claim_job_uuid(self, result):
        """Claim a ``job_uuid`` so a redelivered result is a no-op.

        Unchanged from the AMQP consumer, and deliberately so: this is the
        mechanism that makes at-least-once delivery safe. The ``INSERT`` and
        the apply run in the same transaction, so a crash after the apply but
        before the commit leaves no ledger row and the next delivery retries
        cleanly; a delivery after a successful commit finds the row and skips.

        :return: ``True`` when this delivery is the first for the job_uuid,
            ``False`` when it was already applied (or the result has no
            job_uuid to claim on).
        """
        job_uuid = result.get("job_uuid")
        if not job_uuid:
            _logger.warning("invoice_agent: result carries no job_uuid — skipped")
            return False
        self.env.cr.execute(
            """
            INSERT INTO invoice_agent_applied_job (job_uuid, applied_at)
            VALUES (%s, NOW())
            ON CONFLICT (job_uuid) DO NOTHING
            """,
            (job_uuid,),
        )
        return self.env.cr.rowcount > 0

    # ------------------------------------------------------------------
    # Move resolution
    # ------------------------------------------------------------------
    @api.model
    def resolve_move(self, result):
        """Find the bill a result belongs to: ``job_uuid`` first, then id.

        ``job_uuid`` is the durable correlation id (it survives a bill being
        renumbered or the worker retrying), so it wins; ``move_id`` is the
        fallback for results that predate the uuid.
        """
        move_model = self.env["account.move"]
        job_uuid = result.get("job_uuid")
        if job_uuid:
            move = move_model.search([("ai_job_uuid", "=", job_uuid)], limit=1)
            if move:
                return move
        move_id = result.get("move_id")
        if move_id:
            move = move_model.browse(move_id)
            if move.exists():
                return move
        return None

    # ------------------------------------------------------------------
    # Live UI status
    # ------------------------------------------------------------------
    @api.model
    def publish_live_status(self, move, status, payload=None):
        """Push a live status notification to the bill's followers via bus.bus.

        Best-effort by design: a bus failure must never fail the result that
        was already applied, nor make the worker retry a job it completed.

        This replaces the module-level ``_publish_live_status`` that used to
        live in ``queue_consumer.py`` (and was imported from
        ``invoice_agent_job.py``); it is a model method now so callers reach it
        through ``self.env`` like every other service, with no cross-module
        import of a private function.
        """
        move.ensure_one()
        try:
            partners = move.message_partner_ids
            if not partners and move.partner_id:
                partners = move.partner_id
            if not partners:
                return
            notification = {
                "type": "invoice_agent_status",
                "status": status,
                "move_id": move.id,
                "job_uuid": move.ai_job_uuid,
                "display_name": move.display_name,
            }
            if payload:
                notification["payload"] = payload
            move.env["bus.bus"]._sendone(partners, "invoice_agent", notification)
            _logger.info(
                "invoice_agent live status: move_id=%d status=%s",
                move.id,
                status,
            )
        except Exception:
            _logger.exception(
                "invoice_agent failed to publish live status for move_id=%d",
                move.id,
            )

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    @api.model
    def apply_result(self, move, result):
        """Write a verified worker result onto ``move``.

        ``result`` is the decoded JWT ``result`` claim::

            {"job_uuid", "move_id", "status": "done",
             "parsed_output": {...}, "usage": {...}, "model": "..."}

        ``move`` is expected to be already company-scoped by the caller
        (``move.with_company(move.company_id)``) — this method does not
        re-scope, so a future caller cannot silently lose the scoping by
        calling a helper that "fixes it up".

        The line handling, the vendor lookup, the rescue rule and the usage
        ledger all go through ``account.move``'s single owners
        (``_line_values_from_payload`` / ``_line_commands`` /
        ``_find_vendor_partner`` / ``_score_and_rescue``), so this path and the
        synchronous apply path cannot drift apart.

        :return: ``True`` once the result is written.
        """
        payload = result.get("parsed_output") or {}
        if not isinstance(payload, dict):
            msg = "parsed_output must be a JSON object"
            raise ValueError(msg)
        move.ensure_one()

        # Score once through the model's shared helper, which also applies the
        # rescue rule (VAT/IBAN filled from the OCR text) — so the worker path
        # and the synchronous path persist exactly the same payload.
        score, _details, payload = move._score_and_rescue(payload)

        partner = move._find_vendor_partner(
            vat=payload.get("vendor_vat"),
            name=payload.get("vendor_name"),
        )

        vals = {
            # ``extraction_json`` is a stored compute of ``ai_extracted_json``
            # — only the source of truth is written.
            "ai_extracted_json": payload,
            "ai_extracted_total": payload.get("amount_total"),
            "ai_confidence": score,
            "ai_review_required": bool(payload.get("review_required")),
            "ai_extraction_status": "extracted",
            "ai_state": "none",  # job round-trip complete
            "ai_model_used": result.get("model"),
            "extraction_model": result.get("model"),
        }
        if partner:
            vals["partner_id"] = partner.id
        # NOTE the key mapping: the extraction payload emits ``due_date`` but
        # the bill field is ``invoice_date_due``. The old hand-rolled mapper in
        # ``_map_extraction_to_move`` read ``invoice_date_due`` from the
        # payload and therefore silently dropped the due date; the mapping is
        # explicit here for that reason.
        for field_name, payload_key in (
            ("invoice_date", "invoice_date"),
            ("invoice_date_due", "due_date"),
            ("ref", "ref"),
        ):
            if payload.get(payload_key):
                vals[field_name] = payload[payload_key]

        line_values = move._line_values_from_payload(payload)
        if line_values:
            # ``_line_commands`` is the single clear-then-create assembler;
            # re-runnable, so a redelivery that got past the ledger cannot
            # double the bill's lines.
            vals["invoice_line_ids"] = move._line_commands(line_values)
        move.write(vals)

        # --- Phase 2: apply the validation verdict when the worker sent one ---
        validation = result.get("validation")
        if isinstance(validation, dict) and validation.get("account_id"):
            move._apply_validation_verdict(validation)

        # Route: a sub-threshold or pipeline-flagged extraction lands in Needs
        # Review with the reason on the chatter.
        threshold, _review = move._get_tiered_thresholds()
        if move.ai_review_required or score < threshold:
            move._flag_needs_review(
                reason=(
                    f"worker extraction confidence {score * 100:.0f}% is below "
                    f"the {threshold * 100:.0f}% routing threshold"
                ),
            )

        # Persist the token/cost ledger row. Never fatal: losing the cost row
        # must not fail a result that was already written.
        try:
            move.env["invoice.llm.service"].log_usage(
                move.id,
                result.get("usage") or {},
                model=result.get("model"),
            )
        except Exception:
            _logger.exception(
                "invoice_agent failed to log result usage for move_id=%s",
                move.id,
            )
        _logger.info(
            "invoice_agent result applied: move_id=%d score=%.2f",
            move.id,
            score,
        )
        return True

    @api.model
    def handle_failed_result(self, result):
        """Handle a signed ``status:"failed"`` result (worker dead-letter).

        Marks the originating outbox row dead so the taskboard shows it, and
        flags the bill for review. Nothing is applied to the bill's data.
        """
        job_uuid = result.get("job_uuid")
        error = result.get("error") or ""
        if job_uuid:
            self.env["invoice.agent.job"]._mark_dead(job_uuid, reason=error)
        move = self.resolve_move(result)
        if move:
            move = move.with_company(move.company_id)
            move.write(
                {
                    "ai_extraction_status": "failed",
                    "ai_error_message": error[:2000] if error else False,
                },
            )
            try:
                move._flag_needs_review(
                    reason=f"extraction was dead-lettered by the worker: {error}",
                )
            except Exception:
                _logger.exception(
                    "invoice_agent: failed to flag move_id=%d for review",
                    move.id,
                )
            self.publish_live_status(move, "failed", result)
        _logger.warning(
            "invoice_agent: failed result for uuid=%s: %s",
            job_uuid,
            error[:200] if error else "no error detail",
        )
        return True

    # ------------------------------------------------------------------
    # Entry point — called by POST /invoice_agent/result
    # ------------------------------------------------------------------
    @api.model
    def handle_payload(self, payload):
        """Verify and apply one posted result envelope.

        ``payload`` is the JSON body the worker posts: ``{"token": "<jwt>"}``
        where the JWT carries the ``result`` claim. The same route serves all
        three lifecycle messages, because they are the same signed envelope:

        * ``status == "extracting"`` — live UI only, nothing is claimed.
        * ``status == "failed"``     — outbox row dead + bill flagged.
        * anything else              — a completed extraction to apply.

        :return: a JSON-serialisable outcome dict. The outcome is *data*, not
            an exception, because none of the branches above is a server
            error; only a malformed or unverifiable request is refused, and
            that is signalled to the caller so the worker can log it.
        """
        token = payload.get("token") if isinstance(payload, dict) else None
        result = self.verify_token(token)
        if result is None:
            return {
                "ok": False,
                "reason": "invalid_token",
                "error": "invalid or missing result token",
            }

        job_uuid = result.get("job_uuid")
        status = result.get("status")

        if status == "extracting":
            move = self.resolve_move(result)
            if move:
                self.publish_live_status(
                    move.with_company(move.company_id),
                    "extracting",
                    result,
                )
            return {"ok": True, "status": "extracting", "job_uuid": job_uuid}

        if status == "failed":
            self.handle_failed_result(result)
            return {"ok": True, "status": "failed", "job_uuid": job_uuid}

        if not self.claim_job_uuid(result):
            # Idempotency guard: a redelivered done-result for an already
            # applied job_uuid is a no-op — never a second draft.
            _logger.info(
                "invoice_agent: duplicate result for uuid=%s — skipped",
                job_uuid,
            )
            return {"ok": True, "duplicate": True, "job_uuid": job_uuid}

        move = self.resolve_move(result)
        if not move:
            _logger.warning(
                "invoice_agent: no move for result uuid=%s — releasing claim",
                job_uuid,
            )
            # Nothing was applied, so the claim must not stick: release it so a
            # later delivery of the same job_uuid can retry once the bill
            # exists. (The old thread rolled the whole transaction back, which
            # released the claim as a side effect; behind a request the
            # controller returns 200, so the release has to be explicit.)
            self.env.cr.execute(
                "DELETE FROM invoice_agent_applied_job WHERE job_uuid = %s",
                (job_uuid,),
            )
            return {
                "ok": False,
                "reason": "no_move",
                "error": "no matching bill for this result",
                "job_uuid": job_uuid,
            }

        # Apply inside the bill's own company. The route runs as the API-key
        # user (or the public user for auth='none'), not as a superuser with an
        # empty context, so company-dependent fields and record rules behave
        # the way they do everywhere else in the module.
        move = move.with_company(move.company_id)
        self.apply_result(move, result)
        self.publish_live_status(move, "ready", result)
        return {
            "ok": True,
            "status": "done",
            "move_id": move.id,
            "job_uuid": job_uuid,
        }
