"""Regression tests for the defects found in the native-ORM review.

Each test pins a *specific* previously-broken behaviour so the fix cannot
silently regress. They are deliberately narrow: they assert on the exact
mechanism the review identified, not on broad end-to-end output (which the
other suites already cover).

Covered:

* P0-1 - ``_cron_extract_pending_bills`` must not roll back a successful
  extraction (the old ``finally: rollback()`` discarded every result).
* P0-2 - applying the same extraction payload twice must not duplicate the
  bill's invoice lines.
* P0-3 - accepting the suggested *total* must replace the lines, not append
  a second copy on top of them.
* P1-1 - vendor-derived text must be HTML-escaped before it reaches the
  chatter (stored-XSS vector via an uploaded PDF).
* P2-5b - the high-effort second pass runs at most once per bill.

The Claude API and Tesseract are never touched: the LLM call is patched and
the OCR text is seeded directly on the record.
"""

import json
import types
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

# A balanced extraction payload: two lines summing to the grand total, so it
# passes the line-sum guard and scores above the routing threshold.
BALANCED_PAYLOAD = {
    "company_name": "ACME Supplies LLC",
    "vendor_name": "ACME Supplies LLC",
    "amount_total": 1350.0,
    "subtotal": 1350.0,
    "invoice_date": "2026-07-01",
    "invoice_date_due": "2026-07-31",
    "overall_confidence": 0.95,
    "extraction_confidence": 0.95,
    "notes": None,
    "review_required": False,
    "lines": [
        {
            "name": "Server hosting",
            "quantity": 1.0,
            "price_unit": 850.0,
            "confidence": 0.95,
        },
        {
            "name": "Setup fee",
            "quantity": 1.0,
            "price_unit": 500.0,
            "confidence": 0.95,
        },
    ],
}

BALANCED_OCR_TEXT = (
    "ACME SUPPLIES LLC\nServer hosting 1 850.00\nSetup fee 1 500.00\nTOTAL 1,350.00"
)


def ensure_chart_of_accounts(env):
    """Load the Generic COA when none is configured (CI has no demo data)."""
    company = env.company
    if not company.chart_template:
        env["account.chart.template"].try_loading(
            "generic_coa",
            company=company,
            install_demo=False,
        )
    env.flush_all()


def fake_messages_response(payload):
    """Shape a stand-in for the Anthropic SDK response object."""
    text = json.dumps(payload)
    content = types.SimpleNamespace(text=text)
    return types.SimpleNamespace(content=[content])


@tagged("post_install", "-at_install")
class TestExtractionRegressions(TransactionCase):
    """Pin the P0/P1/P2 defects found in the architecture review."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_chart_of_accounts(cls.env)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "ACME Supplies LLC",
                "company_id": False,
            },
        )
        journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )
        if not journal:
            journal = cls.env["account.journal"].create(
                {
                    "name": "Regression Purchase Journal",
                    "type": "purchase",
                    "code": "TRJ",
                },
            )
        cls.journal = journal
        cls.journal.write({"ai_agent_enabled": True, "ai_min_confidence": 0.80})
        cls.env.flush_all()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _attachment(self, name="regression-bill.pdf"):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "raw": b"%PDF-1.4 regression fixture",
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": 0,
            },
        )

    def _draft_bill(self, **overrides):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "ai_source_attachment_id": self._attachment().id,
        }
        vals.update(overrides)
        return self.env["account.move"].create(vals)

    # ------------------------------------------------------------------
    # P0-1: the extraction cron must not discard a successful extraction
    # ------------------------------------------------------------------
    def test_extraction_cron_does_not_rollback_success(self):
        """A successful extraction must survive the cron unchanged.

        The old implementation ended every record with
        ``finally: rollback(); commit()`` - which threw away the extraction it
        had just written and left the bill stuck in ``processing``. This
        asserts both halves of the fix: no rollback is issued for a successful
        record, and the status actually advances.
        """
        move = self._draft_bill(
            ai_extraction_status="processing",
            ocr_state="done",
            ocr_text=BALANCED_OCR_TEXT,
        )
        rollbacks = []

        with (
            patch.object(self.cr, "rollback", lambda: rollbacks.append(1)),
            patch.object(self.cr, "commit", lambda: None),
            patch.object(
                self.env["account.move"].__class__,
                "_claude_messages_create",
                return_value=fake_messages_response(BALANCED_PAYLOAD),
            ),
        ):
            self.env["account.move"]._cron_extract_pending_bills(batch_size=5)

        self.assertEqual(
            rollbacks,
            [],
            "a successful extraction must never be rolled back",
        )
        move.invalidate_recordset()
        self.assertEqual(move.ai_extraction_status, "extracted")

    # ------------------------------------------------------------------
    # P0-2: applying a payload must be idempotent
    # ------------------------------------------------------------------
    def test_applying_payload_twice_does_not_duplicate_lines(self):
        """Payload -> lines is replace-not-append, so re-runs are safe.

        ``_apply_extraction_payload`` is re-entrant (the high-effort second
        pass, a queue redelivery and a manual re-run all call it). With an
        unconditional ``Command.create`` each run appended a second copy of
        every line and doubled the bill total.
        """
        move = self._draft_bill()

        move._apply_extraction_payload(dict(BALANCED_PAYLOAD))
        first_pass = len(move.invoice_line_ids)
        move._apply_extraction_payload(dict(BALANCED_PAYLOAD))
        second_pass = len(move.invoice_line_ids)

        self.assertEqual(first_pass, 2)
        self.assertEqual(
            second_pass,
            first_pass,
            "re-applying the same payload must not add lines",
        )
        self.assertAlmostEqual(move.amount_total, 1350.0, places=2)

    # ------------------------------------------------------------------
    # P0-3: accepting the suggested total replaces the lines
    # ------------------------------------------------------------------
    def test_accepting_suggested_total_does_not_append(self):
        """The 'total' chip replaces the lines instead of stacking on them.

        Previously ``apply_suggested_value('amount_total')`` appended the
        suggested lines on top of whatever the bill already had, roughly
        doubling the total.
        """
        move = self._draft_bill()
        move.write(
            {
                "ai_extracted_json": dict(BALANCED_PAYLOAD),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Pre-existing line",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                        },
                    ),
                ],
            },
        )
        self.assertEqual(len(move.invoice_line_ids), 1)

        move.apply_suggested_value("amount_total")

        self.assertEqual(
            len(move.invoice_line_ids),
            2,
            "the suggested set must replace the existing lines, not append",
        )
        self.assertAlmostEqual(move.amount_total, 1350.0, places=2)

    # ------------------------------------------------------------------
    # P1-1: vendor-derived text must be escaped in the chatter
    # ------------------------------------------------------------------
    def test_review_chatter_escapes_vendor_derived_text(self):
        """HTML from a scanned document must be escaped, not rendered.

        ``_flag_needs_review`` interpolates the reason and the extraction's
        'notes' - both ultimately derived from OCR of a vendor-supplied PDF.
        Unescaped, a crafted document stores a live ``<script>`` on the bill.
        """
        move = self._draft_bill(
            ai_confidence_notes="<img src=x onerror=alert(1)>",
        )
        move._flag_needs_review(reason="vendor <script>alert(1)</script> said so")

        body = "\n".join(move.message_ids.mapped("body"))
        self.assertNotIn("<script>", body, "raw script tag must not be stored")
        self.assertNotIn("<img src=x", body, "raw img tag must not be stored")
        # The escaped forms are assembled from fragments so the assertion
        # cannot be silently rewritten into a contradiction.
        escaped_script = "&" + "lt;script" + "&" + "gt;"
        escaped_img = "&" + "lt;img"
        self.assertIn(escaped_script, body, "reason text must survive, escaped")
        self.assertIn(escaped_img, body, "notes text must survive, escaped")

    # ------------------------------------------------------------------
    # P2-5b: the high-effort pass runs at most once per bill
    # ------------------------------------------------------------------
    def test_high_effort_pass_runs_at_most_once(self):
        """The second pass is guarded by a plain boolean, not a compute.

        The guard used to live inside the stored ``ai_confidence_details``
        compute, so writing those details re-ran the compute that owned the
        guard. It is now a plain field the compute cannot rewrite.
        """
        move = self._draft_bill(
            ai_extraction_status="extracted",
            ai_extracted_json=dict(BALANCED_PAYLOAD),
            ocr_text=BALANCED_OCR_TEXT,
            ai_high_effort_attempted=True,
        )
        # Would hit the Claude client if the guard did not short-circuit.
        self.assertFalse(move._run_high_effort_pass(0.80))

    # ------------------------------------------------------------------
    # P2-6: one stored payload, one serialization
    # ------------------------------------------------------------------
    def test_extraction_json_is_derived_from_the_stored_payload(self):
        """``extraction_json`` is a derived view of ``ai_extracted_json``.

        They were written independently and could diverge (one held the
        rescued payload, the other the raw one). Now only the source is
        written and the text view follows it.
        """
        move = self._draft_bill()
        self.assertFalse(move.extraction_json)

        move.write({"ai_extracted_json": dict(BALANCED_PAYLOAD)})

        self.assertTrue(move.extraction_json)
        self.assertEqual(
            json.loads(move.extraction_json)["amount_total"],
            BALANCED_PAYLOAD["amount_total"],
        )

    # ------------------------------------------------------------------
    # P1-4: the cron claim locks its rows (no double-processing)
    # ------------------------------------------------------------------
    def test_claim_helpers_only_return_matching_rows(self):
        """The SKIP LOCKED claims return exactly the eligible rows."""
        pending = self._draft_bill(ocr_state="pending")
        self._draft_bill(ocr_state="done")
        # No source attachment -> never claimable.
        self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
                "ocr_state": "pending",
            },
        )

        claimed = self.env["account.move"]._claim_pending_ocr(limit=10)

        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed.id, pending.id)

    # ------------------------------------------------------------------
    # P2-8: stuck detection uses the dedicated processing timestamp
    # ------------------------------------------------------------------
    def test_stuck_domain_prefers_processing_timestamp(self):
        """A fresh chatter write must not make a stuck bill look healthy.

        The domain ages records off ``ai_processing_started_at`` rather than
        ``write_date``, which any chatter post or confidence recompute bumps.
        """
        stale = self._draft_bill(
            ai_extraction_status="processing",
            ocr_state="done",
            ai_processing_started_at="2020-01-01 00:00:00",
        )
        domain = self.env["account.move"]._stuck_domain(
            "ai_extraction_status",
            "processing",
            "2026-01-01 00:00:00",
        )
        found = self.env["account.move"].search(domain)
        self.assertIn(stale, found, "the stale bill must be recycled")
