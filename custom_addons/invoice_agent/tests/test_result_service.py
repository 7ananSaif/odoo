"""Tests for the HTTP result intake (Wave 3, review finding P1-3).

Two layers are covered:

1. **The service** (``models/result_service.py``): token verification, the
   ``invoice_agent_applied_job`` idempotency ledger, and the release-on-no-move
   rule that makes a ``409`` safe for the worker to retry.
2. **The route** (``controllers/main.py``, ``POST /invoice_agent/result``):
   the status code each outcome maps to, exercised over real HTTP with
   ``HttpCase`` — including the negative paths the worker's retry ladder
   depends on (400 and 401 permanent, 409 transient).

Why the secret is not hardcoded anywhere here: the module reads the shared
secret through **one owner**, ``invoice.llm.service._jwt_secret()``, and that
owner consults ``INVOICE_AI_JWT_SECRET`` in the environment *before* the
``invoice_agent.jwt_secret`` parameter. A test that signed with a literal would
mint tokens this deployment's verifier rejects — which is exactly the bug the
pre-existing ``test_llm_service`` JWT error demonstrates. So the helpers below
ask the owner for the secret, and one test pins the env-before-parameter
precedence deliberately.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt

from odoo.addons.invoice_agent.models.result_service import (
    RESULT_AUDIENCE,
    RESULT_ISSUER,
    RESULT_SUBJECT,
)
from odoo.tests import HttpCase, tagged

from .test_extraction import InvoiceAgentTestCommon

# A known-good secret used only for the precedence test, which monkeypatches
# the environment variable the owner reads first.
ENV_OVERRIDE_SECRET = "invoice-agent-test-env-secret-0123456789abcdef"

# The secret the suite installs as the ``invoice_agent.jwt_secret`` config
# parameter so the tests run on a fresh CI database with no ``.env`` at all.
# 32+ bytes keeps HMAC-SHA256 from warning. ``_jwt_secret`` prefers the
# ``INVOICE_AI_JWT_SECRET`` env var, so a deployment configured through
# ``.env`` still resolves its own value.
TEST_JWT_SECRET = "invoice-agent-test-jwt-secret-0123456789abcdef"


def _mint(
    payload,
    secret,
    *,
    audience=RESULT_AUDIENCE,
    issuer=RESULT_ISSUER,
    subject=RESULT_SUBJECT,
    expires_in=timedelta(seconds=300),
):
    """Mint a result token exactly like ``invoice-ai/app/result_signing.py``."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": now,
            "exp": now + expires_in,
            "result": payload,
        },
        secret,
        algorithm="HS256",
    )


def _ledger_row_exists(env, job_uuid):
    """True when the idempotency ledger still holds ``job_uuid``."""
    env.cr.execute(
        "SELECT 1 FROM invoice_agent_applied_job WHERE job_uuid = %s",
        (job_uuid,),
    )
    return bool(env.cr.fetchall())


# ---------------------------------------------------------------------------
# Service layer — models/result_service.py
# ---------------------------------------------------------------------------
@tagged("post_install", "-at_install")
class TestResultService(InvoiceAgentTestCommon):
    """Verification, ledger and release semantics, with no HTTP involved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Make the suite self-contained: CI installs the addon on a fresh DB
        # with no .env, so set the shared secret as the config parameter before
        # any caller resolves it. ``_jwt_secret`` reads the env var first, so a
        # deployment configured through .env still wins.
        cls.env["ir.config_parameter"].sudo().set_param(
            "invoice_agent.jwt_secret",
            TEST_JWT_SECRET,
        )
        cls.service = cls.env["invoice.agent.result.service"]
        # The deployment's real secret, from the single owner both sides use.
        cls.secret = cls.env["invoice.llm.service"]._jwt_secret()

    def _bill(self, **overrides):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "invoice_date": "2026-07-01",
            "journal_id": self.purchase_journal.id,
            # NOT 'processing': ``action_request_ai_extraction`` refuses a bill
            # that already has an extraction running. Starting from 'pending'
            # and enqueuing is the real lifecycle, and it leaves the bill in
            # 'processing' — the state these tests exercise.
            "ai_extraction_status": "pending",
        }
        vals.update(overrides)
        return self.env["account.move"].create(vals)

    # ------------------------------------------------------------------
    # verify_token
    # ------------------------------------------------------------------
    def test_a_valid_token_is_verified(self):
        token = _mint({"job_uuid": "u-1", "status": "done"}, self.secret)

        result = self.service.verify_token(token)

        self.assertIsNotNone(result)
        self.assertEqual(result["job_uuid"], "u-1")
        self.assertEqual(result["status"], "done")

    def test_a_token_signed_with_another_secret_is_rejected(self):
        token = _mint({"job_uuid": "u-1"}, "not-the-shared-secret-at-all-000")

        self.assertIsNone(self.service.verify_token(token))

    def test_a_token_for_another_audience_is_rejected(self):
        token = _mint(
            {"job_uuid": "u-1"},
            self.secret,
            audience="some.other.service",
        )

        self.assertIsNone(self.service.verify_token(token))

    def test_a_token_with_the_wrong_subject_is_rejected(self):
        token = _mint({"job_uuid": "u-1"}, self.secret, subject="extract.other")

        self.assertIsNone(self.service.verify_token(token))

    def test_an_expired_token_is_rejected(self):
        token = _mint(
            {"job_uuid": "u-1"},
            self.secret,
            expires_in=timedelta(seconds=-600),
        )

        self.assertIsNone(self.service.verify_token(token))

    def test_a_missing_token_is_rejected(self):
        self.assertIsNone(self.service.verify_token(False))
        self.assertIsNone(self.service.verify_token(""))

    def test_a_token_without_a_result_claim_is_rejected(self):
        token = jwt.encode(
            {
                "iss": RESULT_ISSUER,
                "aud": RESULT_AUDIENCE,
                "sub": RESULT_SUBJECT,
                "exp": datetime.now(UTC) + timedelta(seconds=300),
            },
            self.secret,
            algorithm="HS256",
        )

        self.assertIsNone(self.service.verify_token(token))

    def test_the_environment_variable_wins_over_the_parameter(self):
        """Pin the precedence the owner documents: env first, parameter second.

        Both sides must agree on which copy wins, or a deployment can set one
        and be silently verified against the other.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "invoice_agent.jwt_secret",
            "the-parameter-secret-0000000000000000",
        )

        with patch.dict(os.environ, {"INVOICE_AI_JWT_SECRET": ENV_OVERRIDE_SECRET}):
            self.assertEqual(
                self.env["invoice.llm.service"]._jwt_secret(),
                ENV_OVERRIDE_SECRET,
            )
            service = self.env["invoice.agent.result.service"]
            accepted = _mint({"job_uuid": "u-env"}, ENV_OVERRIDE_SECRET)
            rejected = _mint(
                {"job_uuid": "u-param"},
                "the-parameter-secret-0000000000000000",
            )
            self.assertIsNotNone(service.verify_token(accepted))
            self.assertIsNone(service.verify_token(rejected))

    # ------------------------------------------------------------------
    # claim_job_uuid — the at-least-once ledger
    # ------------------------------------------------------------------
    def test_a_job_uuid_can_only_be_claimed_once(self):
        payload = {"job_uuid": "claim-me-once"}

        self.assertTrue(self.service.claim_job_uuid(payload))
        self.assertFalse(
            self.service.claim_job_uuid(payload),
            "a redelivered result must not claim the same uuid twice",
        )

    def test_a_result_without_a_job_uuid_cannot_be_claimed(self):
        self.assertFalse(self.service.claim_job_uuid({"status": "done"}))

    # ------------------------------------------------------------------
    # handle_payload — the release-on-no-move rule
    # ------------------------------------------------------------------
    def test_no_matching_bill_releases_the_claim(self):
        """A 409 must not poison the job_uuid.

        The worker retries a 409 later, once the bill exists. If the claim
        stuck, that retry would be swallowed as a duplicate and the result
        would be lost forever.
        """
        payload = {"job_uuid": "no-bill-yet", "status": "done", "move_id": 999999}

        first = self.service.handle_payload({"token": _mint(payload, self.secret)})
        self.assertFalse(first["ok"])
        self.assertEqual(first["reason"], "no_move")
        self.assertFalse(
            _ledger_row_exists(self.env, "no-bill-yet"),
            "the ledger row must be deleted so a retry can succeed",
        )

        second = self.service.handle_payload({"token": _mint(payload, self.secret)})
        self.assertEqual(
            second["reason"],
            "no_move",
            "the second delivery must be attempted, not skipped as a duplicate",
        )

    def test_a_done_result_is_applied_to_its_bill(self):
        move = self._bill()
        move.action_request_ai_extraction()
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "done",
            "parsed_output": {
                "vendor_name": "ACME Supplies LLC",
                "amount_total": 1350.0,
                "lines": [
                    {"name": "Server hosting", "quantity": 1.0, "price_unit": 850.0},
                ],
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "claude-opus-4-8",
        }

        outcome = self.service.handle_payload({"token": _mint(payload, self.secret)})

        self.assertTrue(outcome["ok"], outcome)
        move.invalidate_recordset()
        self.assertEqual(move.ai_extraction_status, "extracted")
        self.assertEqual(move.ai_extracted_total, 1350.0)
        self.assertEqual(len(move.invoice_line_ids), 1)

    def test_a_redelivered_done_result_is_a_noop(self):
        move = self._bill()
        move.action_request_ai_extraction()
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "done",
            "parsed_output": {"vendor_name": "ACME Supplies LLC", "amount_total": 10.0},
            "model": "claude-opus-4-8",
        }
        token = _mint(payload, self.secret)

        first = self.service.handle_payload({"token": token})
        second = self.service.handle_payload({"token": token})

        self.assertTrue(first["ok"])
        self.assertTrue(second.get("duplicate"), second)

    def test_an_extracting_status_writes_nothing(self):
        move = self._bill()
        move.action_request_ai_extraction()
        # ``action_request_ai_extraction`` only enqueues the outbox row; it
        # does not flip the status itself. Capture whatever the status is and
        # assert the result delivery left it alone — that is the property.
        before = move.ai_extraction_status
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "extracting",
        }

        outcome = self.service.handle_payload({"token": _mint(payload, self.secret)})

        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["status"], "extracting")
        move.invalidate_recordset()
        self.assertEqual(
            move.ai_extraction_status,
            before,
            "a lifecycle ping must never move the bill's state",
        )

    def test_a_failed_status_marks_the_outbox_row_dead(self):
        move = self._bill()
        move.action_request_ai_extraction()
        job = self.env["invoice.agent.job"].search(
            [("job_uuid", "=", move.ai_job_uuid)],
            limit=1,
        )
        self.assertTrue(job)
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "failed",
            "error": "bad schema",
        }

        outcome = self.service.handle_payload({"token": _mint(payload, self.secret)})

        self.assertTrue(outcome["ok"])
        job.invalidate_recordset()
        self.assertEqual(job.state, "dead")
        self.assertIn("bad schema", job.dead_reason or "")
        move.invalidate_recordset()
        self.assertEqual(move.ai_extraction_status, "failed")

    def test_an_invalid_token_never_touches_the_bill(self):
        move = self._bill()
        move.action_request_ai_extraction()
        before = move.ai_extraction_status

        outcome = self.service.handle_payload({"token": "not-a-token"})

        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason"], "invalid_token")
        move.invalidate_recordset()
        self.assertEqual(move.ai_extraction_status, before)


# ---------------------------------------------------------------------------
# Route layer — POST /invoice_agent/result
# ---------------------------------------------------------------------------
@tagged("post_install", "-at_install")
class TestResultRoute(HttpCase):
    """The status codes the worker's retry ladder keys off."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Self-contained config: the shared secret lives in the parameter so
        # the suite runs on a fresh CI DB with no .env. HttpCase runs its HTTP
        # requests on this test cursor, so the route handler resolves the same
        # secret this class signed with.
        cls.env["ir.config_parameter"].sudo().set_param(
            "invoice_agent.jwt_secret",
            TEST_JWT_SECRET,
        )
        cls.secret = cls.env["invoice.llm.service"]._jwt_secret()
        cls.purchase_journal = cls.env["account.journal"].search(
            [
                ("type", "=", "purchase"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        if not cls.purchase_journal:
            cls.purchase_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Purchase Journal",
                    "type": "purchase",
                    "code": "TPJ",
                },
            )

    def _post_result(self, body):
        """POST a JSON body to the result route (no auth header, by design)."""
        return self.url_open(
            "/invoice_agent/result",
            method="POST",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )

    def _bill(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.env.ref("base.main_partner").id,
                "invoice_date": "2026-07-01",
                "journal_id": self.purchase_journal.id,
                # See TestResultService._bill: enqueuing from 'pending' is the
                # real lifecycle; 'processing' would be rejected as a second run.
                "ai_extraction_status": "pending",
            },
        )
        move.action_request_ai_extraction()
        return move

    def test_a_non_object_body_returns_400(self):
        response = self.url_open(
            "/invoice_agent/result",
            method="POST",
            data="[1, 2, 3]",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)

    def test_a_missing_token_returns_401(self):
        response = self._post_result({})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])

    def test_a_forged_token_returns_401(self):
        response = self._post_result(
            {"token": _mint({"job_uuid": "u"}, "wrong-secret-0000000000000000")},
        )

        self.assertEqual(response.status_code, 401)

    def test_an_unknown_bill_returns_409(self):
        payload = {"job_uuid": "route-no-bill", "status": "done", "move_id": 999999}

        response = self._post_result({"token": _mint(payload, self.secret)})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["reason"], "no_move")

    def test_a_done_result_returns_200_and_applies(self):
        move = self._bill()
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "done",
            "parsed_output": {
                "vendor_name": "ACME Supplies LLC",
                "amount_total": 42.0,
            },
            "model": "claude-opus-4-8",
        }

        response = self._post_result({"token": _mint(payload, self.secret)})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        move.invalidate_recordset()
        self.assertEqual(move.ai_extraction_status, "extracted")

    def test_an_extracting_ping_returns_200(self):
        move = self._bill()
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "extracting",
        }

        response = self._post_result({"token": _mint(payload, self.secret)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "extracting")

    def test_a_failed_result_returns_200(self):
        move = self._bill()
        payload = {
            "job_uuid": move.ai_job_uuid,
            "move_id": move.id,
            "status": "failed",
            "error": "dead-lettered",
        }

        response = self._post_result({"token": _mint(payload, self.secret)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
