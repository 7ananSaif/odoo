# Extraction Accuracy — Run Records

Every number in this table maps back to the exact prompt bytes in
`custom_addons/invoice_agent/prompts/`. To reproduce a run:

```bash
# from the repo root, inside the rebuilt odoo image
python scripts/eval_extraction.py --prompt custom_addons/invoice_agent/prompts/v1.md --input text
python scripts/eval_extraction.py --prompt custom_addons/invoice_agent/prompts/v1.md --input document
python scripts/eval_extraction.py --prompt custom_addons/invoice_agent/prompts/v2.md --input text
```

Each invocation writes a JSON run record when `--out runs/<name>.json` is
passed (e.g. `runs/v1-text.json`).

## Week-7: confidence calibration and threshold tuning

The week-7 milestone (v0.7) added a **calibrated confidence score** to every
extraction and a production-size golden set. The eval script now answers two
questions the milestone needs:

1. **Is the self-reported certainty calibrated?** The goldens carry
   ``field_confidence`` (per field group + overall) — the model's *own*
   certainty statements. The harness compares stated certainty against per-
   invoice correctness and reports a point-biserial correlation. A strong
   positive correlation means the model's "I'm 95% sure" is informative; a
   near-zero one means the stated floats are noise and the routing threshold
   must lean on the deterministic blend instead — the "calibrate, don't
   trust" lesson of the brief.

2. **What does the threshold curve look like?** For 0.70 / 0.80 / 0.90 the
   script computes auto-approval rate and error rate among approved records,
   for both the *stated* score and the *calibrated blend*
   (``models/confidence.py``: arithmetic line-sum against the subtotal,
   per-country VAT regex rescue, ISO-13616 IBAN rescue, OCR per-word conf,
   self-report blend). ``--curve paths.csv`` dumps the numbers.

### Golden set

- **20 invoices** under `custom_addons/invoice_agent/tests/fixtures/golden_set.json`:
  the original 10 clean multi-currency invoices, 5 new clean ones (AED, EUR,
  SGD, BRL, PLN), and **5 deliberately awful scans** (ids prefixed
  `awful_`): a blurred totals section, a rotated/torn header, duplicated
  lines, truncated quantity columns, and contrast-inverted characters. The
  awful set is what proves low-confidence bills really land in Needs Review.
- Offline mode derives the frozen answer **per invoice** from its own ground
  truth: clean scans extract every field correctly with a high (0.95)
  self-report; awful scans keep the same items but lose the totals section
  and *honestly* state a low 0.55 overall. That variance is what makes the
  calibration correlation measurable in CI.

### Threshold tuning in production

The eval curve is the offline twin of the production query
`custom_addons/invoice_agent/scripts/tune_threshold.sql`, which joins
`invoice_agent_usage` (the Claude call ledger) to `account_move` and computes
auto-approval vs error rate at 0.70 / 0.80 / 0.90 on real volume. The chosen
threshold is committed as the `invoice_agent.confidence_threshold`
ir.config_parameter (Settings → Invoice Agent → Confidence Routing). It
overrides the per-journal `ai_min_confidence` and can be changed at runtime —
the zero-downtime rollback path for a bad threshold.

### Known calibration sharp edges

- The arithmetic cross-check compares line items against the **subtotal**,
  never the tax-inclusive grand total — lines sum to the net on a VAT
  invoice. Fall back to `amount_total` only for grand-total-only layouts.
- A torn totals section (both subtotal and TOTAL unreadable) scores low
  because the math check has no sane target — that is the signal that should
  land the bill in Needs Review, not a silent pass.

## Convention

- Overall accuracy = correct fields / total fields across the golden set
  (20 invoices × 9 fields = 180 field slots; `lines` counts when all lines
  for the invoice match positionally).
- `fields` column shows per-field precision (best / worst).
- Run records are kept under `runs/` and referenced by timestamp.

## Table

| Date (UTC) | Prompt | Input | Overall | Best field | Worst field | Avg latency ms | Run record |
|---|---|---|---|---|---|---|---|
| — | `prompts/v1.md` | text | pending | pending | pending | pending | pending |
| — | `prompts/v1.md` | document | pending | pending | pending | pending | pending |
| — | `prompts/v2.md` | text | pending | pending | pending | pending | pending |

Live runs require `ANTHROPIC_API_KEY`. Offline runs (default, no key) replay
a frozen answer and are deterministic for CI — they validate the harness, not
the model.

## Notes for the next iteration

- The winning prompt version (v1 vs v2) is chosen on these numbers, not on
  feel. When both are close, prefer the one with stable worst-field accuracy
  (the `worst_field` column).
- Keep the instructions block byte-identical between v1 and v2 — the only
  diff is the few-shot example; changing both levers at once would make the
  A/B meaningless.
- Re-run after any prompt edit and append the new row; do not overwrite
  historical rows. That is what makes "every accuracy number maps back to
  exact prompt bytes" auditable.
