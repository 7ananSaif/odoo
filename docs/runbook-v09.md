# v0.9 Cutover Runbook — Async Extraction Pipeline Live

Purpose: bring the full stack up (Postgres → RabbitMQ → Odoo → worker) so a
scanned invoice flows Odoo outbox → `extract.request` → async Claude
extraction → signed `extract.done` → live-status draft, **surviving worker
and broker restarts mid-batch**. Every step here is idempotent and
re-runnable.

---

## 1. Container start order

`docker compose` resolves dependencies for you, but the ordering contract is:

1. **db** (Postgres) — must be healthy before Odoo boots.
2. **rabbitmq** — must be healthy before the worker publishes/consumes and
   before the topology init.
3. **odoo** — depends on `db healthy`; declares the cron crons (outbox
   drain, OCR, extraction) and starts the result-consumer thread via
   `post_load`.
4. **worker** — depends on `rabbitmq healthy`; `python -m app.consumer`
   re-declares the topology on connect and every reconnect.
5. **invoice-ai** (HTTP service) — independent; workers call it only if a
   synchronous fallback path is used.
6. **nginx / certbot** — reverse proxy + TLS (unchanged from v0.3 mount).

```bash
# From the repo root on EC2:
docker compose up -d --build
docker compose ps        # every service must report "Up (healthy)"
```

The topology is declared **idempotently** by `invoice_queue/topology.py`
(topic exchange, DLX, retry ladder, dead queue) and re-declared by the
worker on every reconnect. Run it once explicitly so the management UI and
any publisher are consistent before traffic flows:

```bash
docker compose exec worker python -m app.consumer --check-topology   # or:
docker compose run --rm --entrypoint python invoice-ai \
    /app/topology_check.py
```

(For an explicit one-shot declaration without a long-running consumer:

```bash
docker compose exec worker python -c \
  "import sys; sys.path.insert(0, '/srv/invoice-ai'); from app.amqp import *; import asyncio, aio_pika; from app.amqp import declare_topology; \
   async def d():\
     c = await aio_pika.connect_robust('amqp://guest:guest@rabbitmq:5672/');\
     await declare_topology(c.channel()); await c.close()\
   asyncio.run(d())"
```
)

## 2. Worker health checks

The compose file defines a `worker` service with `restart: unless-stopped`;
liveness is verified by watching the worker log and the queue depth:

```bash
docker compose logs -f worker | grep "invoice-ai worker: consuming"
docker compose exec rabbitmq rabbitmqctl list_queues name messages_ready \
    messages_unacknowledged consumers state
```

Expected after drain: `invoice.extract` ready≈0, consumers=1, state=healthy;
`retry.*` and `invoice.extract.dead` at 0 until a poison/probe message lands.

## 3. Feature flag — synchronous fallback

`action_request_ai_extraction()` (the Extract button) enqueues via the
transactional outbox. To revert to the synchronous path instantly without a
release, add an `ir.config_parameter`:

```
invoice_agent.async_extraction_enabled = True   # default True on v0.9
```

The controller reads it; when False, `action_request_ai_extraction()`
calls the legacy synchronous `invoice.llm.service.extract_invoice` path.
Rollback of the flag = `set_param(..., 'False')` — no image deploy needed.

## 4. Trace one invoice on paper

1. Accountant uploads a scanned PDF → controller creates a draft
   `account.move` (`ai_extraction_status='pending'`, OCR cron claims it).
2. OCR cron (`invoice_agent.cron_ocr_pending_bills`) runs Tesseract,
   stores `ocr_text`, marks `ocr_state='done'`.
3. Extract button → `_enqueue_ai_job()` writes an `invoice.agent.job` row
   (state `pending`, `job_uuid` UNIQUE) on the SAME cursor.
4. Drain cron (`invoice.agent.job._cron_drain_outbox`) publishes
   `extract.request` to `invoice.agent` with `{move_id, attachment_id,
   attempt, job_uuid, ocr_text}` (persistent, `delivery_mode=2`); stamps
   `published_at`, flips row `sent`, pushes *queued* bus.bus status.
5. Worker (prefetch=1) consumes it, publishes `extract.started`
   (*extracting* live status), runs Claude (AsyncAnthropic), publishes the
   JWT-signed `extract.done` on `extract.done`.
6. Odoo result-consumer thread verifies the JWT, resolves the move by
   `ai_job_uuid`, `INSERT ... ON CONFLICT DO NOTHING` on the
   applied-jobs ledger, applies header+lines in a fresh cursor, pushes
   *ready* status. One draft, exactly once.
7. Confidence routing: Auto or Needs Review kanban based on threshold.

## 5. Failure drill (mid-batch survival)

1. **Kill the worker mid-batch**:
   `docker compose kill worker; docker compose start worker`. Unacked jobs
   redeliver (at-least-once); the applied-jobs ledger dedupes them — a
   double-processed job never creates a second draft.
2. **Stop RabbitMQ**:
   `docker compose stop rabbitmq`. The worker's `connect_robust` reattaches
   (`reconnect_interval=5`) when the broker returns. Outbox rows stay
   `pending` — they are NOT lost; the drain cron republishes them.
3. **Force a poison PDF** into the DLQ: publish a job whose body fails
   `ExtractionValidationError` (e.g. corrupt OCR text). Watch it land in
   `invoice.extract.dead` with an `x-death` header while the signed
   `status:"failed"` result flags the move for review.
4. **Idempotency proof** (SQL):
   ```sql
   SELECT ai_job_uuid, COUNT(*) FROM account_move
   WHERE ai_extraction_status IN ('extracted','validated')
   GROUP BY ai_job_uuid HAVING COUNT(*) > 1;
   -- must return 0 rows
   ```

## 6. Rollback

- Feature flag off (see §3) restores the synchronous path without deploy.
- `git revert` + redeploy returns to the v0.8 topology script if the DLX
  drift proves problematic (declarations raise 406 PRECONDITION_FAILED if
  queue arguments changed — that is the drift alarm).

## 7. Baseline (throughput/cost)

Before tagging v0.9, record: invoices-per-minute and cost-per-invoice from
the `invoice.agent.usage` ledger + queue drain times. These are the RAG
week's regression baselines.
