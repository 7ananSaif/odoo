# Queue & Result Contract — `invoice.agent`

Pins the wire contract between the Odoo outbox, RabbitMQ, the aio-pika
worker, and the Odoo result intake. Both sides must stay in lockstep with
THIS document, not with each other's code.

Topology source of truth: `invoice_queue/topology.py` (exchange, queues,
bindings, declaration order). Message schemas: this document.

**There is one AMQP direction and one HTTP direction.** Odoo *sends* jobs on
the broker; the worker *returns* results over HTTP. They are different
transports on purpose (§3.1) and neither side should be "simplified" into the
other without re-reading that section.

---

## 1. Topology

| Kind      | Name                   | Type   | Durable | Binding / Arguments                       |
|-----------|------------------------|--------|---------|-------------------------------------------|
| exchange  | `invoice.agent`        | topic  | yes     | —                                         |
| exchange  | `invoice.extract.dlx`  | direct | yes     | dead-letter exchange for `invoice.extract`|
| queue     | `invoice.extract`      | —      | yes     | `extract.request`; `x-dead-letter-exchange=invoice.extract.dlx`, `x-dead-letter-routing-key=extract.dead`, `x-delivery-limit=3` |
| queue     | `retry.5s`             | —      | yes     | DLX `retry.retry.5s`; `x-message-ttl=5000`, DLX back to `invoice.agent`/`extract.request` |
| queue     | `retry.30s`            | —      | yes     | DLX `retry.retry.30s`; TTL 30 000 ms, DLX back to `extract.request` |
| queue     | `retry.5m`             | —      | yes     | DLX `retry.retry.5m`; TTL 300 000 ms, DLX back to `extract.request` |
| queue     | `invoice.extract.dead` | —      | yes     | `extract.dead` on both exchanges           |

Declared idempotently by `invoice_queue/topology.py` and re-declared by the
worker after every robust reconnect.

There is **no `invoice.result` queue** (Wave 3, review finding P1-3). Results
travel over HTTP — §3. A broker provisioned before that change still holds the
queue and its `extract.started` / `extract.done` bindings, because AMQP has no
"undeclare"; `invoice_queue.topology.delete_result_queue()` removes them, by
hand.

### 1.1 Retry ladder semantics (v0.9)

* The retry delay is the queue's `x-message-ttl` — expiry dead-letters the
  message back to `invoice.agent`/`extract.request`, re-entering
  `invoice.extract`. No worker timers.
* `x-delivery-limit: 3` is the crash safety net: an unacked message
  (worker killed mid-job) redelivers at most 3 times, then the broker
  itself dead-letters it to `invoice.extract.dead`. A poison PDF can never
  loop forever.
* Routing keys on the DLX: `retry.retry.5s`, `retry.retry.30s`,
  `retry.retry.5m`, `extract.dead`.

### 1.2 Ack / nack policy (v0.9 rewrite)

| Outcome                          | Action                          |
|----------------------------------|---------------------------------|
| Success                          | ack                             |
| Transient (429/5xx/connection)   | publish DLX → retry tier (by attempt), ack original |
| Permanent (bad schema/malformed) | publish DLX → `extract.dead` + POST a signed `status:"failed"` result, ack original |
| Unknown / no attempt counter     | discard (ack, no republish)     |
| Crash between publish and ack    | redelivery — idempotent by `job_uuid` ledger |
| Crash redelivery > `x-delivery-limit` | broker dead-letters autonomously |

## 2. Request message (AMQP)

### `extract.request` — Odoo outbox → worker (`invoice.extract` queue)

Published by `queue.publisher.publish_extract_request` when the drain cron
(`invoice.agent.job._drain_pending`) drains the transactional outbox.

```json
{
  "move_id": 123,
  "attachment_id": 456,
  "attempt": 1,
  "job_uuid": "9f2c…",
  "ocr_text": "INVOICE 2026-01 …"
}
```

- `job_uuid` — durable correlation id, echoed back on every result; generated
  by `account.move._enqueue_ai_job` and stored in `account.move.ai_job_uuid`.
- `ocr_text` — OCR already ran Odoo-side (`_cron_ocr_pending_bills`); the
  worker never touches PDFs.
- Persisted message (`delivery_mode=2`): survives broker restarts.

## 3. Result delivery (HTTP)

### 3.1 Why HTTP, not a broker queue

Odoo used to run a `pika.SelectConnection` consumer thread in **every**
process (started from `post_load`), drain `invoice.result`, and apply the
result on a hand-built environment. That cost:

* one AMQP connection + one io-loop thread **per Odoo process** — eight of
  each on an eight-worker deployment, for one logical consumer;
* a database name that had to be guessed (`INVOICE_AGENT_DB` → `odoo.conf` →
  "whichever registry is loaded"), because the thread had no request to
  select one;
* `SUPERUSER_ID` with an empty context, so every write bypassed record rules
  and company scoping;
* a thread that could die silently, with no restart.

A request already *has* a database, a user, a company and a context. The
native answer for "an external service finished" is a webhook — see
`addons/account_invoice_extract/controllers/main.py::request_done`. So the
result direction is a webhook now, and the *request* direction stayed on the
broker: Odoo initiates it, and it needs the durability, ordering and retry
ladder that a queue provides and an HTTP call to a possibly-down worker does
not.

### 3.2 Transport

| Item        | Value                                                |
|-------------|------------------------------------------------------|
| Method/route| `POST /invoice_agent/result`                         |
| Auth        | `auth='none'` + HS256 signature check (§5). The signature **is** the authentication. |
| CSRF        | disabled — not a browser form; a cross-site post cannot mint a valid signature |
| Body        | `{"token": "<jwt>"}`                                 |
| Sender      | `invoice-ai/app/odoo_result.py` (`OdooResultClient`) |
| Receiver    | `invoice.agent.result.service.handle_payload`        |

Worker-side configuration (`invoice-ai/app/config.py`, `INVOICE_AI_` prefix):

| Setting                       | Default                    | Meaning                     |
|-------------------------------|----------------------------|-----------------------------|
| `INVOICE_AI_ODOO_BASE_URL`    | `http://odoo:8069`         | Odoo base URL               |
| `INVOICE_AI_ODOO_RESULT_PATH` | `/invoice_agent/result`    | webhook path                |
| `INVOICE_AI_ODOO_RESULT_TIMEOUT_SECONDS` | `30.0`           | per-request timeout         |

### 3.3 Response codes, and what the worker does with each

The worker turns Odoo's status code straight into a retry-ladder decision
(`InvoiceConsumer._classify_delivery_failure` in `invoice-ai/app/consumer.py`).

| Code | Meaning                                             | Worker action |
|------|-----------------------------------------------------|---------------|
| 200  | Applied, already applied (duplicate), dead-letter recorded, or `extracting` acknowledged | ack — the job is finished |
| 400  | Body was not a JSON object / malformed envelope      | **permanent** → dead-letter; retrying cannot fix it |
| 401  | Token missing, expired, or signed with the wrong secret | **permanent** → dead-letter; a secret mismatch is a configuration fault and must surface, not be hammered |
| 409  | Token valid, but no bill matches it **yet**          | **transient** → ride the retry ladder |
| 429, 5xx | Odoo overloaded / broken                        | **transient** → ride the retry ladder |
| transport error | connection refused, DNS, timeout         | **transient** → ride the retry ladder |

Every non-2xx response carries `{"ok": false, "reason": ...}` so the failure is
legible in the worker log.

409 is safe to retry precisely because the receiver **releases** its
idempotency claim when it finds no bill (§6.3).

## 4. Lifecycle payloads

All three messages share one envelope — a signed JWT whose `result` claim is
the payload — so there is one signing path and one verification path.

### 4.1 `status: "extracting"`

Sent before the Claude call so the UI flips to a live *extracting* state.

```json
{ "job_uuid": "9f2c…", "move_id": 123, "status": "extracting" }
```

**Best-effort.** If this delivery fails, the worker logs a warning and
continues with the extraction; a missed UI update must never cost the job.
The receiver publishes to `bus.bus` and writes nothing.

### 4.2 `status: "done"`

The only envelope that carries data.

```json
{
  "job_uuid": "9f2c…",
  "move_id": 123,
  "status": "done",
  "parsed_output": { "vendor_name": "...", "lines": [...], "amount_total": 0 },
  "usage": { "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0 },
  "model": "claude-opus-4-8",
  "attempt": 1,
  "validation": { "account_id": 0, "account_confidence": 0 },
  "validation_usage": { "cache_read_input_tokens": 0 }
}
```

`validation` / `validation_usage` are omitted entirely when the RAG pass was
skipped or failed — the absence is meaningful and the receiver treats it as
"no verdict".

### 4.3 `status: "failed"`

Sent when the worker dead-letters a job (permanent failure or an exhausted
ladder), so the dead-letter is visible in the Odoo taskboard and not only in
the RabbitMQ management UI.

```json
{ "job_uuid": "9f2c…", "move_id": 123, "status": "failed", "error": "…" }
```

## 5. JWT signing rule

- Shared secret: `INVOICE_AI_JWT_SECRET` (worker) ==
  `invoice_agent.jwt_secret` (Odoo `ir.config_parameter`), HS256. Resolved by
  one owner on each side (`llm_service._setting` / `_jwt_secret`), so the two
  cannot drift.
- Claims, pinned identically in `invoice-ai/app/result_signing.py` and
  `models/result_service.py`:

| Claim    | Value               | Enforced by |
|----------|---------------------|-------------|
| `iss`    | `invoice-ai`        | receiver (issuer check) |
| `aud`    | `odoo.invoice-agent`| receiver (audience check) |
| `sub`    | `extract.done`      | receiver (explicit compare) |
| `exp`    | send time + 300 s   | receiver (10 s leeway) |
| `result` | the payload dict    | receiver (must be a dict) |

- The token is minted immediately before each delivery, not at job start, so
  its 300 s lifetime only has to outlive clock skew plus the request itself.
- A rejected token is a **rejection, not a traceback**: `verify_token` returns
  `None`, the route answers `401`, and nothing is written.
- Same secret family as the outbound `/v1/extract` JWT, but a separate
  audience (`odoo.invoice-agent` vs `invoice-ai`) so a token minted for one
  direction can never be replayed on the other.

## 6. Odoo result-intake rules

Owner: `models/result_service.py`, model `invoice.agent.result.service`.
Entry point `handle_payload(body)`; the route only maps its outcome to a
status code.

### 6.1 Routing by status

| `result.status`   | Behaviour |
|-------------------|-----------|
| `"extracting"`    | publish a live `bus.bus` status; claim nothing, write nothing |
| `"failed"`        | `handle_failed_result`: mark the outbox row dead (`_mark_dead`), set `ai_extraction_status='failed'` + `ai_error_message`, flag the bill for review. Never writes extraction fields. |
| anything else     | a completed extraction — claim, resolve, apply (§6.3) |

### 6.2 Failures never bleed into data

A rejected signature, a missing `job_uuid` or an unresolvable bill each stop
before the write path. The apply helper (`apply_result`) is only reachable
after a token verified *and* a bill resolved.

### 6.3 Idempotency guard

Before applying a completed result, the receiver runs
`INSERT INTO invoice_agent_applied_job (job_uuid) VALUES (%s, NOW()) ON
CONFLICT (job_uuid) DO NOTHING` in the same transaction as the apply.

- Zero rows inserted ⇒ already applied ⇒ the redelivery is a no-op, never a
  second draft `account.move`. The 200 response says `{"duplicate": true}`.
- Row insert + apply commit together, so a crash mid-apply leaves no ledger
  row and the next delivery retries safely.
- **Release on no-move.** If the claim succeeds but no bill matches, the
  receiver `DELETE`s the ledger row before answering `409`. The old consumer
  thread got this for free by rolling the transaction back; behind a request
  the rollback would also discard the claim *and* the response, so the release
  is explicit. Without it, the first 409 would poison the `job_uuid` forever.
- The ledger is `invoice_agent_applied_job`; each delivery's `job_uuid` is a
  `UNIQUE` key, so double-claiming one uuid is impossible at the SQL layer.

### 6.4 Scoping

The apply runs inside the bill's own company (`move.with_company(
move.company_id)`) under the request's real user, so company-dependent fields
and record rules behave as everywhere else in the module — not as
`SUPERUSER_ID` with an empty context.

### 6.5 Shared-owner rule

The apply path does not re-implement anything the model already owns. Line
handling, the vendor lookup, the rescue rule and the scoring all go through
`account.move`'s single owners (`_line_values_from_payload`, `_line_commands`,
`_find_vendor_partner`, `_score_and_rescue`), so the worker path and the
synchronous apply path cannot drift apart.

## 7. Shared constants (must never drift)

| Constant                | Value                 | Files                                  |
|-------------------------|-----------------------|----------------------------------------|
| `EXCHANGE_NAME`         | `invoice.agent`       | `invoice_queue/topology.py`, `queue_publisher.py`, `app/amqp.py` |
| `ROUTING_KEY_REQUEST`   | `extract.request`     | same                                   |
| `QUEUE_EXTRACT`         | `invoice.extract`     | `invoice_queue/topology.py`, `app/amqp.py` |
| `QUEUE_DEAD`            | `invoice.extract.dead`| `invoice_queue/topology.py`, `app/amqp.py`, `app/retry.py` |
| `DLX_EXCHANGE`          | `invoice.extract.dlx` | `invoice_queue/topology.py`, `app/amqp.py`, `app/retry.py` |
| `ROUTING_KEY_DEAD`      | `extract.dead`        | same                                   |
| `RETRY_TIERS`           | `retry.5s`/`retry.30s`/`retry.5m` | `invoice_queue/topology.py`, `app/amqp.py`, `app/retry.py` |
| `DELIVERY_LIMIT`        | 3                     | same                                   |
| Result route            | `/invoice_agent/result` | `controllers/main.py`, `app/config.py` (`odoo_result_path`) |
| Applied-jobs ledger      | `invoice.agent.applied.job` | `invoice_agent_applied_job.py`, `result_service.py` |
| `RESULT_AUDIENCE`       | `odoo.invoice-agent`  | `app/result_signing.py`, `result_service.py` |
| `RESULT_ISSUER`         | `invoice-ai`          | same                                   |
| `RESULT_SUBJECT`        | `extract.done`        | same                                   |
| `RESULT_TTL_SECONDS`    | 300                   | `app/result_signing.py`                |

`ROUTING_KEY_STARTED` / `ROUTING_KEY_DONE` / `QUEUE_RESULT` were deleted in
Wave 3 — they named a queue and two routes that no longer exist. Do not
reintroduce them.

CI drift check: the FastAPI test suite + `scripts/check_openapi_drift.py`
re-validate the shared schema; the addon suite exercises
`invoice.agent.result.service` end to end (`tests/test_controllers.py`), and
the worker suite pins the delivery classification
(`invoice-ai/tests/test_retry.py::test_transient_delivery_failure_rides_the_ladder`
and `::test_permanent_delivery_failure_dead_letters`).
