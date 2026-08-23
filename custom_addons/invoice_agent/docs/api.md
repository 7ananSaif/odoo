# invoice_agent — External API Reference

This document is the contract for machine-to-machine integrations against the
`invoice_agent` module. It documents the two transport layers you can use, the
single stable create-method (`account.move.create_from_extraction`), the field
mapping between payload keys and ORM fields, and the error codes the facade
returns.

| Transport | Endpoint | Auth | Deprecation status |
|---|---|---|---|
| XML-RPC | `/xmlrpc/2/common`, `/xmlrpc/2/object` | `login` + password/API key | Deprecated, removed in Odoo 22 (fall 2028) — see [External API docs](https://www.odoo.com/documentation/19.0/developer/reference/external_api.html#migrating-from-xml-rpc-json-rpc) |
| JSON-2 (external) | `/json/2/<model>/<method>` | `Authorization: Bearer <api-key>` (+ `X-Odoo-Database`) | Current Odoo 19 recommendation |
| JSON-RPC (controller) | `POST /invoice_agent/upload`, `POST /invoice_agent/status/<id>` | Bearer API key | Module-specific endpoints, not the deprecated `/jsonrpc` service |

> JSON-RPC (`type='jsonrpc'`) controllers are **not** affected by the XML-RPC /
> JSON-RPC deprecation. The `/xmlrpc*` and `/jsonrpc` *services* are.

---

## 1. Quick start

```bash
# 1. Create an API key: Preferences -> Account Security -> New API Key
#    (global key; scope NULL matches every scope check, incl. 'rpc')
KEY=... python scripts/client_demo.py \
    --host https://invoices.<domain> \
    --database <db> \
    --login admin \
    --pdf-file bill.pdf
```

The demo uploads a PDF, polls the extraction status, then reads the created
bill twice: once over XML-RPC (`search_read`) and once over the Odoo 19
`/json/2/account.move/read` endpoint.

---

## 2. Transport comparison — XML-RPC vs JSON-2

### 2.1 Authentication

**XML-RPC** — two-step: `common.authenticate(db, login, password, {})` returns
a `uid`, then every `object.execute_kw(db, uid, password, ...)` call re-sends
the credentials. The API key is passed **in place of the password**:

```python
import xmlrpc.client

common = xmlrpc.client.ServerProxy("https://host/xmlrpc/2/common")
uid = common.authenticate(db, "admin", API_KEY, {})   # -> 2

models = xmlrpc.client.ServerProxy("https://host/xmlrpc/2/object")
moves = models.execute_kw(
    db, uid, API_KEY,
    "account.move", "search_read",
    [[("id", "=", 42)]],
    {"fields": ["name", "ai_extraction_status", "ai_confidence"], "limit": 5},
)
```

**JSON-2** — stateless per-request Bearer auth. The key rides in the
`Authorization: bearer <key>` header; the database in `X-Odoo-Database`
(only needed on multi-db servers). No `uid`, no `login`:

```python
import requests

resp = requests.post(
    "https://host/json/2/account.move/read",
    headers={
        "Authorization": f"bearer {API_KEY}",
        "X-Odoo-Database": "prod",
        "Content-Type": "application/json",
    },
    json={"ids": [42], "fields": ["name", "ai_extraction_status", "ai_confidence"]},
)
moves = resp.json()   # raw return value of read(); no JSON-RPC envelope
```

### 2.2 Body shape

| | XML-RPC `execute_kw` | JSON-2 |
|---|---|---|
| Method call | `execute_kw(db, uid, key, model, method, args, kwargs)` | `POST /json/2/<model>/<method>` |
| Record ids | First element of `args` (`[[('id','=',42)]]` for `search_read`, `[[42]]` for `read`) | Top-level `"ids"` field |
| Named kwargs | 7th positional argument (dict): `fields`, `limit`, `offset`, ... | Top-level JSON keys — **all args are named; there are no positional args** |
| Context | `{"context": {...}}` inside kwargs | Top-level `"context"` field |
| `@api.model` methods | No record ids in `args` | Omit/empty `ids` |
| Response envelope | Single XML `<methodResponse>` | **Raw** return value of the method (list/dict), no wrapper |
| Error body | XML-RPC `fault` | HTTP 4xx/5xx + `{"name", "message", "arguments", "debug"}` |

The `/json/2` endpoint cannot chain calls: **one request = one transaction**.
Method selection and multi-step checks (search then modify) must be wrapped in
a single model method — exactly what `create_from_extraction` is for.

### 2.3 Argument serialization limits

| Limitation | XML-RPC | JSON-2 |
|---|---|---|
| Binary payloads | base64-encoded strings only | JSON strings only (upload PDFs via the `multipart` upload route, not JSON-2) |
| `datetime` | `DateTime` type; Odoo converts `fields.Datetime` to string | Strings (`"2026-08-02 00:00:00"` or ISO) |
| One2many writes | `[(0, 0, {...})]` command lists, ugly to build | Same ORM command format; must be valid JSON |
| `None` | Supported (`allow_none=True` / `<nil/>`) | Native `null` |
| Floats/precision | XML-RPC `double` | Native JSON numbers |
| Large responses | XML parser overhead, entity limits | JSON, no envelope overhead |

### 2.4 Access-rights enforcement

Both transports run against the **same ORM layer for the same user**, so access
rights are enforced identically *inside* the model call:

- Model-level ACLs (`ir.model.access`) gate `create/read/write/unlink`.
- Field-level rights (`ir.model.fields` `groups`) gate individual fields.
- **Record rules** (`ir.rule`) filter recordsets — including the
  multi-company rule (`account_move_comp_rule`) that restricts bills to the
  user's companies.

**Where they differ is the failure surface:**

| Failure | XML-RPC | JSON-2 |
|---|---|---|
| Invalid credentials | `Fault: AccessDenied` (an XML-RPC `fault`; the traceback is a string argument) | HTTP 401 `{"name": "...Unauthorized", "message": "Invalid apikey"}` |
| Record-rule filtered-out record | `Fault: AccessError` with the full traceback in `faultString` | HTTP 403 with `AccessError` fields (`debug` carries the traceback) |
| Missing model/method | `Fault: AttributeError` / `NotFound` | HTTP 404/405 |
| Bad payload | `Fault: TypeError`/`ValueError` + traceback | HTTP 400/422 + `{"message", "arguments", "debug"}` |

Practical consequence: JSON-2 exposes the same `AccessError` semantics but
delivers them as **HTTP statuses with machine-readable JSON**, while XML-RPC
wraps everything as an XML `fault` whose distinguishing signal is the string
content of `faultString`. A client that must branch on *reason* (denied vs
missing) should prefer JSON-2 and match on `message`/`name`.

---

## 3. Endpoints

### 3.1 `POST /invoice_agent/upload`

Machine route (`type='http'`, `auth='none'` + bearer decorator,
`csrf=False`, `save_session=False`).

Request:

```http
POST /invoice_agent/upload HTTP/1.1
Authorization: Bearer <api-key>
Content-Type: multipart/form-data

file=@bill.pdf  (type=application/pdf, max 10 MiB)
```

Responses:

| Status | Body |
|---|---|
| 201 | `{"jsonrpc": "2.0", "id": null, "result": {"move_id": 42, "name": "VEND/...", "state": "draft", "ai_extraction_status": "processing"}}` |
| 400 | `{"error": {"message": "..."}}` — missing `file`, non-PDF mimetype, >10 MiB |
| 401 | `{"error": {"message": "..."}}` — missing/invalid/revoked/wrong-scope key |

### 3.2 `POST /invoice_agent/status/<move_id>`

JSON-RPC controller route (`type='jsonrpc'`, `auth='bearer'`). Machine clients
poll with the API key; interactive browser sessions also work (bearer falls
back to session only when the Sec-Fetch browser headers are present).

Request body: `{"jsonrpc": "2.0", "method": "call", "id": 1, "params": {}}`

Response `result`:

```json
{
  "move_id": 42,
  "ai_extraction_status": "processing",
  "ai_confidence": 0.0,
  "ai_review_required": false
}
```

A poller treats any of `extracted`, `validated`, `failed` as terminal.

---

## 4. `account.move.create_from_extraction` — the stable facade

Instead of raw ORM writes from integrators, create a draft vendor bill through
one `@api.model` method. It is callable from **both** transports with an
identical payload:

```python
# XML-RPC
models.execute_kw(db, uid, API_KEY, "account.move", "create_from_extraction",
                  [payload])   # @api.model → no ids in args

# JSON-2
POST /json/2/account.move/create_from_extraction
Authorization: bearer <key>
X-Odoo-Database: prod
{"payload": {...}}            # named arg
```

### 4.1 Payload contract

```json
{
  "partner_id": 12,
  "invoice_date": "2026-08-01",
  "invoice_date_due": "2026-08-31",
  "ref": "INV-2026-00123",
  "lines": [
    {
      "name": "Consulting — August",
      "product_id": 5,
      "quantity": 1,
      "price_unit": 1200.0,
      "tax_ids": [1, 3]
    }
  ]
}
```

| Key | Type | Required | Maps to |
|---|---|---|---|
| `partner_id` | int | only if no resolvable name | `res.partner` (read-access checked; explicit id wins over name) |
| `partner_name` / `vendor_name` | str | fallback when `partner_id` omitted | `res.partner` search by name (`parent_id = False`, first hit) |
| `invoice_date` | str (YYYY-MM-DD) | no | `account.move.invoice_date` |
| `invoice_date_due` | str | no | `account.move.invoice_date_due` |
| `ref` | str | no | `account.move.ref` |
| `journal_id` | int | no | `account.move.journal_id` (default purchase journal if omitted) |
| `lines[]` | array | **yes, non-empty** | `account.move.invoice_line_ids` |
| `lines[].name` | str | yes, unless `product_id` given | line label |
| `lines[].product_id` | int | yes, unless `name` given | `product_id` on the line |
| `lines[].quantity` | number | no (default 1.0) | `quantity` |
| `lines[].price_unit` | number | no (default 0.0) | `price_unit` |
| `lines[].tax_ids` | int[] | no | `tax_ids` (id list) |
| `amount_total` | number | no | `ai_extracted_total` (drives variance) |
| `overall_confidence` | number 0..1 | no | `ai_confidence` |
| `notes` | str | no | ambient only — surfaced on the Needs Review chatter via `ai_confidence_notes`; never written into `ai_ocr_text` |

The created move always starts in `ai_extraction_status = 'pending'` inside the
extraction state machine. Once a queue consumer runs the extraction, the
calibrated routing fields become available (see §5).

> **Week-7 note:** `notes` used to be stored in `ai_ocr_text` by
> `create_from_extraction` and `_apply_extraction_payload`. That was a bug —
> the raw OCR text is what the confidence layer re-scores against, and
> overwriting it with the model's ambiguity notes silently changed the score
> on the next compute. Both writers now leave `ai_ocr_text` alone.

### 4.2 Success response

```json
{
  "success": true,
  "id": 42,
  "name": "VEND/2026/08/0001",
  "ai_extraction_status": "pending"
}
```

### 4.3 Error codes

Errors are returned as a **dict with HTTP 200** — the facade never raises for
application-level failures, so a transport-level 4xx/5xx is reserved for auth
and routing problems.

| Code | Meaning |
|---|---|
| `E4001` | `payload` is not a JSON object |
| `E4002` | `lines` missing, not a list, or empty |
| `E4003` | a line is not an object, or lacks both `name` and `product_id` |
| `E4004` | `partner_id` unknown or not readable (record rules / ACL applied) |
| `E4005` | `journal_id` does not exist |
| `E4221` | ORM create failed (validation, required field, constraint) |

Body: `{"success": false, "error_code": "E4001", "message": "..."}`.

---

## 5. Field reference (what integrators read)

Expose these from the move after extraction:

| Field | Type | Meaning |
|---|---|---|
| `ai_extraction_status` | selection | `pending` → `processing` → `extracted` → `validated` / `failed` |
| `ai_confidence` | float 0..1 | overall extraction confidence |
| `ai_review_required` | boolean | human review flagged |
| `ai_extracted_total` | monetary | amount the AI read off the document |
| `ai_amount_variance` | monetary | `ai_extracted_total - amount_total` |
| `ai_variance_pct` | float | relative variance |
| `ai_needs_review` | boolean | variance beyond the journal's `ai_min_confidence` threshold |
| `ai_error_message` | text | last pipeline error (set on `failed`) |
| `confidence_score` | float 0..1 | **week 7:** calibrated blend — arithmetic line-sum vs OCR conf vs self-report + VAT/IBAN rescue. This is the score the routing threshold compares against |
| `ai_extraction_state` | selection | **week 7:** kanban routing state — auto (cleared threshold), needs_review (sub-threshold / failed / unscored), approved (human validated) |
| `ai_confidence_details` | json | **week 7:** audit trail — every input, the blend weights, verified cross-checks, and which fallback path fired (high_effort, rescue:vat, rescue:iban, arithmetic) |
| `ai_confidence_notes` | text | **week 7:** the model's ambiguity notes, surfaced verbatim on the Needs Review chatter message |
| `ai_ocr_text` | text | raw OCR text — never overwritten by the pipeline (see the week-7 note under §4.1) |
| `ai_extracted_json` | json | the normalized Claude payload (see §4.1) |
| `ai_source_attachment_id` | many2one | the uploaded PDF |

> Note for learners: the checklist mentions `extraction_confidence` — that is
> the *internal* name used across this project's docs and tests for the
> normalized payload key. The stored model field is `ai_confidence`.
