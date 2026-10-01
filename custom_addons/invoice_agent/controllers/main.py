"""HTTP + JSON-RPC endpoints for the invoice_agent module.

This file is the *teaching core* of the module: it exercises every piece of
the Odoo 19 HTTP stack documented in ``docs/tutorial_http_controllers.md``:

* ``@http.route(type='http', auth='bearer', methods=['POST'], csrf=False)``
* ``@http.route(type='jsonrpc', auth='bearer')`` -- Odoo 19: ``type='json'``
  is a deprecated alias, see the ``route()`` decorator in ``odoo/http.py``.
  ``auth='bearer'`` accepts a session (interactive browser, which sends the
  Sec-Fetch headers) or, for machine clients, an ``Authorization: Bearer``
  API key — the status poll route is a machine endpoint, same as upload.
* Reading ``request.httprequest.files`` from a ``multipart/form-data`` POST
* Storing an ``ir.attachment`` with the ``raw`` field (binary, not ``datas``)
* Auth via ``Authorization: Bearer <key>`` resolved against
  ``res.users.apikeys._check_credentials(scope='rpc', key=key)``
* ``request.update_env(user=uid)`` to rebind the ORM environment
* Clean ``werkzeug.exceptions.BadRequest`` / JSON ``Unauthorized`` responses
  instead of leaked tracebacks

Why ``auth='bearer'`` on the upload route:

  ``auth='bearer'`` is Odoo 19's native API-key authentication: it reads the
  ``Authorization: Bearer <key>`` header, resolves it with
  ``res.users.apikeys._check_credentials(scope='rpc', key=key)``, rebinds the
  environment through ``request.update_env(user=uid)`` and sets
  ``session.can_save = False`` -- see ``ir.http._auth_method_bearer``. Using
  it here means the module implements no credential checking at all, and it
  matches ``/invoice_agent/status``, so every route in this API authenticates
  the same way.

  A ``type='http'`` route renders an ``Unauthorized`` as an HTML page by
  default, which a machine client cannot read. ``models/ir_http.py``
  overrides ``ir.http._handle_error`` so error bodies on ``/invoice_agent/*``
  stay JSON; that is what keeps the client contract -- and the JSON-401 tests
  in ``tests/test_controllers.py`` -- intact under the native auth mode.

  ``auth='bearer'`` additionally accepts a browser session for top-level
  navigations carrying the browser's ``Sec-Fetch-*`` headers. That is the
  native behaviour and it is CSRF-safe: a cross-site form post arrives with
  ``Sec-Fetch-Site: cross-site`` and fails the ``check_sec_headers()`` guard
  inside ``_auth_method_bearer``.
"""

import logging
import time

from werkzeug.exceptions import BadRequest, NotFound

from odoo import SUPERUSER_ID, http
from odoo.http import request
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# Upload guards: 10 MiB limit and PDF-only mimetypes.
# Kept as module constants so tests can reach them and so the policy is
# decided in exactly one place.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIMETYPES = ("application/pdf",)


class InvoiceAgentController(http.Controller):
    # ------------------------------------------------------------------
    # POST /invoice_agent/upload  (multipart/form-data, machine route)
    # ------------------------------------------------------------------
    @http.route(
        "/invoice_agent/upload",
        type="http",
        auth="bearer",
        methods=["POST"],
        csrf=False,
        save_session=False,
        readonly=False,
    )
    def invoice_agent_upload(self, **kwargs):
        """Accept a PDF, store it as an ir.attachment, create a draft
        account.move (bill) with ``ai_extraction_status='pending'`` and return
        the new move's id as JSON.

        Note on ``csrf=False`` (justification, mirror of the ``/web/database/*``
        family in ``addons/web/controllers/database.py``): this is a machine
        route authenticated by a bearer API key, not a browser form. CSRF
        protects browser sessions from cross-site form posts; a bearer token in
        the Authorization header is *not* automatically attached by browsers,
        so the classic CSRF attack vector does not apply. Browser form posts
        should stay ``csrf=True`` (the default).
        """
        httprequest = request.httprequest
        remote_addr = httprequest.remote_addr

        upload = httprequest.files.get("file")
        if upload is None:
            _logger.warning("Upload without 'file' part from %s", remote_addr)
            raise BadRequest(
                _("Missing 'file' part in multipart/form-data upload."),
            )

        raw = upload.read() if hasattr(upload, "read") else upload
        filename = upload.filename or "invoice.pdf"
        content_type = (upload.content_type or "").lower()

        if len(raw) > MAX_UPLOAD_BYTES:
            _logger.warning(
                "Rejected oversized upload (%d bytes > %d) from %s",
                len(raw),
                MAX_UPLOAD_BYTES,
                remote_addr,
            )
            raise BadRequest(
                _(
                    "File too large: %(size)d MiB exceeds the %(max)d MiB limit.",
                )
                % {
                    "size": len(raw) // (1024 * 1024),
                    "max": MAX_UPLOAD_BYTES // (1024 * 1024),
                },
            )

        if content_type not in ALLOWED_MIMETYPES:
            _logger.warning(
                "Rejected non-PDF upload (mimetype=%r) from %s",
                content_type,
                remote_addr,
            )
            raise BadRequest(
                _(
                    "Unsupported file type %(mime)s: only %(allowed)s are accepted.",
                )
                % {
                    "mime": content_type or "unknown",
                    "allowed": ", ".join(ALLOWED_MIMETYPES),
                },
            )

        # NOTE: authentication happens in ``ir.http._auth_method_bearer``,
        # before this body runs: the native handler validates the API key and
        # rebinds ``request.env`` to that user. The module therefore performs
        # no credential check of its own. This body used to re-run the entire
        # check a second time, so every upload cost two ``res.users.apikeys``
        # resolution rounds and the two copies were free to drift apart.

        # ---- Store the source document ----
        attachment = request.env["ir.attachment"].create(
            {
                "name": filename,
                "raw": raw,  # Binary field: raw bytes, no base64 dance
                "mimetype": content_type,
                "res_model": "account.move",
                "res_id": 0,  # Unbound until the move exists; linked below
            },
        )

        # ---- Create the draft bill in the extraction state machine ----
        # ``ocr_state`` defaults to 'pending' but is written explicitly so
        # the OCR cron (data/cron.xml) claims the record on its next tick —
        # the contract with the queue is visible in the create call itself.
        move = request.env["account.move"].create(
            {
                "move_type": "in_invoice",  # vendor bill
                "ai_source_attachment_id": attachment.id,
                "ai_extraction_status": "pending",
                "ocr_state": "pending",
                "ai_confidence": 0.0,
            },
        )
        if move:
            # Link the document to the bill AND register it as the bill's main
            # attachment. ``_message_set_main_attachment_id`` stamps
            # ``message_main_attachment_id`` (so the uploaded PDF appears in
            # the bill's chatter and attachment box) and calls
            # ``register_as_main_attachment``, which fills in
            # ``res_model``/``res_id`` — the same hook the native
            # ``account_invoice_extract`` flow hangs off. Previously the PDF
            # was an orphaned attachment with no chatter entry, so an
            # accountant reviewing the bill could not see the source document.
            attachment.write({"res_id": move.id})
            move._message_set_main_attachment_id(
                attachment,
                force=True,
                filter_xml=False,
            )

        # ---- Enqueue the extraction hook (placeholder; the real OCR/Claude
        # work runs on the queue worker). The move is 'pending', which is what
        # the status endpoint reports to polling clients. ----
        try:
            move._invoice_agent_schedule_extraction()
        except Exception:
            # Never turn a queueing error into a client-visible traceback.
            _logger.exception(
                "Failed to enqueue extraction for move %d",
                move.id,
            )

        # ---- Audit trail ----
        _logger.info(
            "invoice_agent upload: move_id=%d attachment_id=%d user=%s uid=%d from %s",
            move.id,
            attachment.id,
            request.env.user.login,
            request.env.uid,
            remote_addr,
        )

        return request.make_json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "move_id": move.id,
                    "name": move.name or "DRAFT",
                    "state": "draft",
                    "ai_extraction_status": move.ai_extraction_status,
                },
            },
            status=201,
        )

    # ------------------------------------------------------------------
    # POST /invoice_agent/result  (invoice-ai worker -> Odoo webhook)
    # ------------------------------------------------------------------
    # Replaces the AMQP result consumer (review finding P1-3). The worker used
    # to publish its signed result to the ``invoice.result`` queue, which Odoo
    # drained with a daemon thread started from ``post_load`` — one thread and
    # one broker connection per Odoo process, an environment rebuilt by hand
    # from ``registry.cursor()``, and a hardcoded database fallback. The worker
    # now POSTs the same signed JWT here instead, and
    # ``models/result_service.py`` verifies and applies it inside this request.
    #
    # Auth mode: ``auth='none'`` + a signature check, not Odoo auth. That is
    # deliberate and mirrors ``account_invoice_extract``'s
    # ``/request_done/<uuid>`` webhook (``auth='public'``): the caller is a
    # machine on the internal network holding the shared HS256 secret, and the
    # signature IS the authentication. ``auth='none'`` is chosen over
    # ``auth='public'`` so the route neither depends on the public user being
    # enabled nor inherits its record rules — the service scopes the write to
    # the bill's own company instead.
    #
    # ``csrf=False`` for the same reason as the upload route: this is not a
    # browser form. A cross-site form post cannot mint a valid HS256 signature,
    # so the CSRF vector does not exist here.
    #
    # ``auth='none'`` has one consequence that is easy to miss and expensive to
    # debug, so it is handled explicitly in the handler: it yields an
    # environment with **no user at all** (``env.user`` is an empty
    # ``res.users``). The ORM defers recomputation to the end of the request
    # and runs it in this very environment (``Environment.default_env``), so a
    # pending compute — and any ``base.automation`` rule it triggers — would
    # later die in ``mail_thread.message_post`` at
    # ``self.env.user._is_public()``: an HTTP 500 raised *after* the result was
    # already written. Binding a real uid for the whole request is therefore
    # mandatory, not cosmetic.
    @http.route(
        "/invoice_agent/result",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        save_session=False,
        readonly=False,
    )
    def invoice_agent_result(self, **kwargs):
        """Accept a signed worker result and apply it to the originating bill.

        Body: ``{"token": "<HS256 JWT>"}`` — the same envelope the worker used
        to publish to ``invoice.result``, so the worker's signing path is
        unchanged. All three lifecycle messages (``extracting`` / ``done`` /
        ``failed``) arrive here; ``invoice.agent.result.service`` decides.

        Status codes, and why each is what it is:

        * ``200`` — processed. Covers an applied result, a duplicate the
          idempotency ledger skipped, and a dead-letter notification: none of
          them should be retried, so none of them is an error.
        * ``401`` — the token is missing, expired, or signed with the wrong
          secret. A *configuration* problem, so it is surfaced loudly; retrying
          cannot fix a secret mismatch.
        * ``409`` — the token is valid but no bill matches it (yet). The claim
          was released, so a later retry is safe and is the right behaviour.
        * ``400`` — the body was not a JSON object.
        """
        try:
            body = request.get_json_data()
        except Exception:
            body = None
        if not isinstance(body, dict):
            _logger.warning(
                "invoice_agent result: non-JSON body from %s",
                request.httprequest.remote_addr,
            )
            return request.make_json_response(
                {"ok": False, "error": "body must be a JSON object"},
                status=400,
            )

        # Bind the request's own environment, not a local one. The deferred
        # recompute described above runs in ``default_env``, which *is* this
        # environment, so a binding that lasted only for the service call would
        # not survive to the flush that triggers the automation. The caller is
        # a machine authenticated by its HS256 signature, so the superuser is
        # the honest identity for it — and ``result_service`` scopes every
        # write to the bill's own company, so the privilege does not spread.
        request.update_env(user=SUPERUSER_ID, su=True)

        outcome = request.env["invoice.agent.result.service"].handle_payload(body)
        status = 200
        if not outcome.get("ok"):
            reason = outcome.get("reason")
            if reason == "invalid_token":
                status = 401
            elif reason == "no_move":
                status = 409
            else:
                status = 400
        return request.make_json_response(outcome, status=status)

    # ------------------------------------------------------------------
    # POST /invoice_agent/measure/trigger  (dev-only measurement route)
    # ------------------------------------------------------------------
    # Dev-only endpoint that exercises the *exact* worker hold of a real
    # Claude call without credentials or API spend: it runs
    # ``invoice.llm.service.extract_invoice`` synchronously inside a regular
    # HTTP worker. When the ``invoice_agent.measure_delay`` config parameter
    # is set (seconds), ``_client()`` sleeps inside the worker for that
    # duration before failing on the missing API key — the elapsed time
    # returned is the proof that one extraction holds one HTTP worker for
    # the full Claude round-trip.
    #
    # Used by scripts/measure_blocking.py (ADR-003 evidence). Not for
    # production use: no authentication, no rate limiting, deliberately
    # minimal.
    # ------------------------------------------------------------------
    @http.route(
        "/invoice_agent/measure/trigger",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def invoice_agent_measure_trigger(self, **kwargs):
        """Run one synchronous Claude client-construction inside this worker.

        Returns the wall-clock time the worker spent inside the Claude call
        path (the ``measure_delay`` sleep in ``invoice.llm.service._client``).
        A 200 response with ``elapsed_seconds`` near the configured delay is
        the measured proof that the request occupied a whole worker process
        for the duration — exactly where a real Claude round-trip holds it.

        """
        started = time.monotonic()
        try:
            self.env["invoice.llm.service"].extract_invoice(
                "MEASURE-PLACEHOLDER TEXT",
            )
        except Exception as exc:
            _logger.info(
                "invoice_agent measure trigger: extraction raised %s after %.2fs",
                type(exc).__name__,
                time.monotonic() - started,
            )
        return request.make_json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "endpoint": "/invoice_agent/measure/trigger",
                },
            },
            status=200,
        )

    # ------------------------------------------------------------------
    # POST /invoice_agent/status/<int:move_id>  (JSON-RPC, poll endpoint)
    # ------------------------------------------------------------------
    @http.route(
        "/invoice_agent/status/<int:move_id>",
        type="jsonrpc",
        auth="bearer",
        methods=["POST"],
        csrf=False,
        readonly=False,
    )
    def invoice_agent_status(self, move_id, **kwargs):
        """Return the extraction state and confidence for a bill, so clients
        can poll while OCR + Claude run in the background.

        Odoo 19 detail: ``type='jsonrpc'`` is the current spelling;
        ``type='json'`` is a deprecated alias that emits a DeprecationWarning
        (see the ``route()`` decorator in ``odoo/http.py``).

        Auth mode: ``auth='bearer'`` accepts a session (interactive browser,
        which sends the Sec-Fetch browser headers) or — for machine clients —
        an ``Authorization: Bearer <api-key>`` header. A poller with no
        session and no key gets a JSON-RPC error envelope instead of an HTML
        redirect, like the upload route's JSON 401.

        The JSON-RPC 2.0 envelope is produced by ``JsonRPCDispatcher``: the
        route returns a plain dict and the dispatcher wraps it into
        ``{"jsonrpc": "2.0", "id": ..., "result": {...}}``.
        """
        move = request.env["account.move"].browse(move_id)
        if not move.exists():
            raise NotFound(f"account.move {move_id} does not exist")

        return {
            "move_id": move.id,
            "ai_extraction_status": move.ai_extraction_status,
            "ai_confidence": move.ai_confidence,
            "ai_review_required": move.ai_review_required,
            "ocr_state": move.ocr_state,
            "ocr_confidence": move.ocr_confidence,
            "ocr_error_message": move.ocr_error_message,
        }
