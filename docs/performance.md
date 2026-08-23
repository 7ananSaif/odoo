# Performance: PostgreSQL EXPLAIN, Indexes & Tuning

**Milestone:** v0.5 — "Authenticated API, Tested and Tuned"
**Owner model target:** `account.move` AI Agent Queue (`invoice_agent` addon)
**Charter:** the queue's slowest queries indexed, N+1 computes killed, `pg_stat_statements`
enabled and `postgres.conf` right-sized on EC2. Every claim below is backed by
committed `EXPLAIN (ANALYZE, BUFFERS)` output and `pg_stat_statements` ranks — not memory.

---

## 0. Environment

| Item | Value |
|---|---|
| PostgreSQL | 16 (compose `db` service; postgres:16) |
| Instance (prod) | EC2 `t3.medium` (2 vCPU / 4 GiB), gp3 30 GiB |
| Local measurement host | Windows dev box → docker compose `db` (loopback `127.0.0.1:5432`) |
| Odoo | 19.0, `invoice_agent` v19.0.0.3.0 |
| DB | `v05_perf` (scratch, seeded via `odoo-bin populate`) |

### Observability flags (compose db service)

```yaml
command:
  - postgres
  - -c shared_preload_libraries=pg_stat_statements
  - -c pg_stat_statements.max=10000
  - -c pg_stat_statements.track=all
  - -c track_io_timing=on
  - -c log_min_duration_statement=200
```

Verified live:

```
shared_preload_libraries     = pg_stat_statements
log_min_duration_statement   = 200ms
track_io_timing              = on
pg_stat_statements.max       = 10000
pg_stat_statements.track     = all
```

---

## 1. Acceptance criteria (written before running anything)

| # | Criterion | Pass/Fail | Evidence |
|---|---|---|---|
| A1 | Every route's auth/csrf is reviewed and justified | ☐ | route table in §6 |
| A2 | Every test class's `@tagged` value reviewed | ☐ | test matrix in §6 |
| A3 | Every `index=`/partial index maps to a column actually filtered/sorted by the queue's SQL | ☐ | §3 + §4 index table |
| A4 | Queue slowest queries identified by `pg_stat_statements` (v0.5 before), not by guessing | ☐ | §2 |
| A5 | N+1 computed-field queries eliminated (per-record loop → `_read_group`) with SQL-log evidence | ☐ | §3 |
| A6 | Before/after `EXPLAIN (ANALYZE, BUFFERS)` committed for the queue's `search_read` | ☐ | §4 |
| A7 | `postgres.conf` right-sized for EC2 t3.medium and applied in compose | ☐ | §5 |
| A8 | Full suite green on a fresh scratch DB (`v05_test`), zero failures/warnings | ☐ | §7 |
| A9 | Live endpoint load test: 50 concurrent uploads, no lock waits, indexes hold | ☐ | §5 |

---

## 2. Baseline — profile the queue (BEFORE)

### 2.1 Seed

```bash
# scratch DB with invoice_agent installed + Generic COA
python odoo-bin -c config/odoo.conf -d v05_perf -i invoice_agent --stop-after-init
# seed a handful of vendor bills, then bulk-duplicate to thousands:
python odoo-bin populate -c config/odoo.conf -d v05_perf \
    --models account.move --factors 300
```

### 2.2 Slow-query log (log_min_duration_statement=200)

> Paste the offending SQL + timings from `docker compose logs db` after loading the queue.

### 2.3 `pg_stat_statements` rank

```sql
SELECT queryid, calls, ROUND(total_exec_time::numeric, 1) AS total_ms,
       ROUND(mean_exec_time::numeric, 1) AS mean_ms,
       ROUND((total_exec_time/nullif(calls,0))::numeric, 1) AS per_call_ms,
       shared_blks_hit, shared_blks_read, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

> Paste the top-20 rank table here.

### 2.4 Queue `search_read` BEFORE

> Paste the exact SQL (from `--log-sql`) and `EXPLAIN (ANALYZE, BUFFERS)` here, plus
> latency in ms. Mark each plan node Seq Scan / Index Scan / Bitmap Heap Scan and the
> estimated-vs-actual `rows`.

---

## 3. N+1 fixes

| Compute method | Before (per-record) | After |
|---|---|---|
| `res.partner._compute_ai_invoice_stats` | Python filter loop over `partner.invoice_ids` → 1 query per partner | one `_read_group` aggregate (count + avg) grouped by `partner_id` |
| `account.move._compute_ai_line_confidence_avg` | `invoice_line_ids` fetched per move | one `_read_group` (avg `ai_confidence` per `move_id`) |
| vendor search (`_match_vendor` / `_parse_claude_payload` / facade) | `res.partner.search([('name','ilike',…)])` per record | shared `_vendor_search_domain` helper; trigram index on `res.partner.name` |

> Evidence: `--log-sql` capture before (per-record `SELECT id FROM account_move_line WHERE move_id=…`
> repeated) and after (single grouped `SELECT … GROUP BY …`). `@api.depends` chains audited —
> no full-table recompute: writes to `amount_total` / `ai_confidence` issue a record-scoped
> `UPDATE account_move SET ai_needs_review=… WHERE id IN (…)`, never `WHERE 1=1`.

---

## 4. Index work + measured delta

### 4.1 Odoo `index=` → DDL mapping (teaching reference)

| Source | DDL emitted |
|---|---|
| `field = fields.X(index=True)` / `index="btree"` | `CREATE INDEX <table>__<field>_index ON <table> USING btree (<field>)` |
| `field = fields.X(index="btree_not_null")` | `CREATE INDEX <table>__<field>_index ON <table> USING btree (<field>) WHERE <field> IS NOT NULL` |
| expression/partial (no `index=` support) | model `init()` → `CREATE INDEX … ON <table> USING btree (…) WHERE …` |

### 4.2 Indexes added

| Table / column | Declared | Why (query) |
|---|---|---|
| `account_move.ai_confidence` | `index=True` | queue `Low Confidence` filter `('!', ('ai_confidence','>=',0.8))` |
| `account_move.ai_needs_review` | `index=True` | queue action default filter `search_default_needs_review=1` |
| `account_move.ai_confidence` partial | `init()`: `WHERE ai_confidence < 0.8` | low-confidence subset much smaller than full table |
| `invoice.agent.extraction.line.company_id` | `index=True` | multi-company record rule filters on it |

### 4.3 AFTER — queue `search_read`

> Re-run the exact SQL from §2.4. Paste `EXPLAIN (ANALYZE, BUFFERS)` and the delta table:

| Query | BEFORE (ms) | AFTER (ms) | delta | Buffers before → after |
|---|---|---|---|---|
| queue default (`needs_review`) | | | | |
| `Low Confidence` filter | | | | |
| status group-by | | | | |

### 4.4 When the planner rightly ignores an index

> Note any Seq Scan that stayed: small table, low selectivity (e.g. status filter matching most
> rows), or `ilike '%…%'` on `res.partner.name` (no btree prefix match — trigram GIN now serves it).
> Recording it here is the point — a btree index on a column that is never prefix-searched is dead weight.

---

## 5. postgres.conf tuning (EC2 t3.medium)

| Setting | Value (right-sized) | Rationale |
|---|---|---|
| `shared_buffers` | 1 GB | 25% of 4 GiB |
| `effective_cache_size` | 3 GB | 75% of 4 GiB |
| `work_mem` | 32 MB | per-operation sort/hash; t3.medium |
| `maintenance_work_mem` | 128 MB | autovacuum/DDL |
| `wal_buffers` | 16 MB | 1/64 of shared_buffers, capped 16 MB |
| `random_page_cost` | 1.1 | gp3 SSD |
| `max_wal_size` / `min_wal_size` | 2 GB / 1 GB | checkpoint frequency |
| `max_connections` | 100 | compose + Odoo `workers=4` |

Odoo side: `workers = 4`, `limit_time_real = 600` (compose `odoo` service / odoo.conf).

### 5.1 Load test

> Command + output: 50 concurrent uploads (`ab` or asyncio script) against the live endpoint,
> tailing `docker compose logs -f odoo` and `pg_stat_statements`. Confirm no lock waits
> (`pg_locks` / `wait_event_type='Lock'`), indexes still used, latency/p95.

---

## 6. v0.5 audit tables

### 6.1 Routes

| Route | auth | csrf | Why |
|---|---|---|---|
| `POST /invoice_agent/upload` | `auth='none'` + bearer decorator | `csrf=False`, `save_session=False` | machine route; bearer is the only gate; JSON 401 not HTML login (see controllers/main.py) |
| `POST /invoice_agent/status/<id>` | `auth='bearer'` | n/a (JSON-RPC) | session (browser Sec-Fetch) or bearer key accepted |

### 6.2 Tests

| Module | Class | `@tagged` |
|---|---|---|
| `test_extraction.py` | `TestExtractionFlow` | `("post_install","-at_install")` |
| `test_controllers.py` | `TestInvoiceAgentControllers` | `("post_install","-at_install")` |
| `test_security.py` | `TestInvoiceAgentSecurity` | `("post_install","-at_install")` |
| `test_bulk_wizard.py` | (verify) | (verify) |

### 6.3 Indexes × queries actually issued

| Index | Enabling query (from §2 log / search_read SQL) | Matches? |
|---|---|---|
| `ai_extraction_status` (existing `index=True`) | queue filters `(status, in, …)` + group_by | ☐ |
| `ai_confidence` (new) | Low Confidence filter | ☐ |
| `ai_needs_review` (new) | default needs-review filter | ☐ |
| partial `ai_confidence < 0.8` (new) | Low Confidence filter | ☐ |
| `extraction_line.company_id` (new) | multi-company record rule | ☐ |
| `ai_source_sale_order_id` (existing) | form many2one, not queue-hot | acceptable (FK-like) |

---

## 7. Green suite on clean DB

```bash
python odoo-bin -c config/odoo.conf -d v05_test -i invoice_agent \
    --test-enable --test-tags /invoice_agent --stop-after-init
```

> Paste the final `0 failed, 0 error(s)` / `0 warnings` summary here.

---

## 8. Changelog hooks

- compose db: pg_stat_statements + log_min_duration_statement=200 + track_io_timing (this milestone)
- compose db: loopback `127.0.0.1:5432:5432` for local measurement tooling (this milestone)
- compose db phase-5 settings (shared_buffers etc.) — filled in §5
- `docs/performance.md` created

> Eval run (2026-08-08, text, v1.md): 10.0%

> Eval run (2026-08-10, text, v1.md): 8.3%

> Eval run (2026-08-10, text, v1.md): 97.2%

> Eval run (2026-08-10, text, v1.md): 91.7%
