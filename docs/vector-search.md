# Vector Search on Vendor/GL History (pgvector + Voyage)

v0.10 wires a semantic-search corpus of every **posted** vendor bill into
Postgres via [pgvector](https://github.com/pgvector/pgvector). This is the
groundwork for the v0.11 RAG tool — a "find me the bill where we paid ACME
for server hosting" query answered by cosine similarity over embeddings
instead of an `ILIKE '%hosting%'` scan.

## What exists now

| Component | Where | Notes |
|---|---|---|
| Embedding model | `invoice-ai` service, `app/embeddings.py` | Voyage `voyage-3`, 1024-dim, batching (128/request), 1 retry, dimension assertion |
| Embed API | `invoice-ai` `POST /v1/embed` | JWT-protected (same secret as `/v1/extract`) |
| Odoo embed client | `invoice.llm.service.embed_texts()` | Returns `None` on 503/connection error → deferred, never failed |
| Corpus table | `invoice.agent.vendor.doc` | One row per posted bill, `vector(1024)` column + HNSW cosine index, `UNIQUE(move_id)` |
| Document render | `account.move._build_rag_document()` | Compact one-document-per-bill text |
| Backfill | `ir.cron` "Backfill Vendor-Doc Embeddings" (10 min) | Batch of 100, resume via `ai_indexed`, idempotent upsert |
| Live embed | `account.move.action_post()` override | Best-effort after post; backfill is the safety net |

## Schema bootstrap

The `vector` extension and the `vector(1024)` column are created **twice,
both idempotent**:

1. `docker/initdb/001-vector-extension.sql` — runs once on a fresh compose
   volume (`CREATE EXTENSION IF NOT EXISTS vector` + a 3-row demo table
   proving the rank operators). No-op on existing volumes.
2. `invoice.agent.vendor.doc.init()` — `CREATE EXTENSION IF NOT EXISTS
   vector` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS embedding
   vector(1024)` + `CREATE INDEX IF NOT EXISTS` on every module install or
   upgrade. This is what makes the **CI** service container work: the
   runner's `pgvector/pgvector:pg16` has the binaries but no initdb hook.

The model's `init()` requires the db user to be a superuser. Both compose
(`POSTGRES_USER=odoo`) and CI (`POSTGRES_USER: odoo`) satisfy this.

## Querying

```sql
-- Top-10 most similar posted bills to a semantic query vector
SELECT partner_id, move_id, content,
       1 - (embedding <=> :query_vector) AS similarity
FROM invoice_agent_vendor_doc
ORDER BY embedding <=> :query_vector
LIMIT 10;
```

Odoo wrapper: `invoice.agent.vendor.doc.search_similar(query_vector, limit)`.

Verify the HNSW index is actually used:

```sql
EXPLAIN ANALYZE
SELECT move_id, 1 - (embedding <=> '[0.1, ...]'::vector) AS similarity
FROM invoice_agent_vendor_doc
ORDER BY embedding <=> '[0.1, ...]'::vector
LIMIT 10;
-- expect: "Index Scan using invoice_agent_vendor_doc_embedding_hnsw_idx"
```

## Failure paths

* **Service down at post time** → `_embed_on_post()` swallows, leaves
  `ai_indexed=False`; backfill cron catches up within 10 minutes.
* **Service down during backfill** → `embed_texts()` returns `None`,
  batch returns 0, `ai_indexed` untouched; next tick retries.
* **Service 401 / dimension drift / 4xx** → `UserError` — these are config
  bugs, not transient.
* **Duplicate embed** → `UNIQUE(move_id)` + `ON CONFLICT DO UPDATE`:
  a redelivered job upserts, never creates a second row.

## Manual rank exercise (migration acceptance)

```bash
docker compose exec db psql -U odoo -d odoo \
  -c "SELECT label, embedding <=> '[1,0,0,0]'::vector AS cosine_dist
      FROM demo ORDER BY cosine_dist;"
```

Expected order: `gamma` (0), `alpha` (0), `beta` → ~1.4 — cosine is
scale-invariant, so gamma (same direction, double magnitude) ties alpha.
