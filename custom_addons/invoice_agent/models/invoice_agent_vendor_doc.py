"""Vendor/GL history RAG corpus — pgvector-backed document store.

v0.10 — one ``invoice.agent.vendor.doc`` row per **posted** vendor bill,
carrying a 1024-dim ``voyage-3`` embedding.

The ``embedding`` column is a **declared ORM field** (``Vector``, from
``models/fields_vector.py``) stored as a real PostgreSQL ``vector(1024)``
type, so:

* ``_auto_init`` owns the column's DDL and reconciles it on every upgrade;
* the column is readable and writable through the ORM, and drift between
  the code and the database is detected;
* the pgvector operators (``<=>`` cosine, ``<#>`` inner product, ``<->``
  L2) run directly on it.

This replaced a raw ``ALTER TABLE ... ADD COLUMN embedding vector(1024)``
in ``init()``. That older shape worked, but the column was invisible to the
ORM, so the model got none of the three things above. Declaring the field is
non-destructive on an existing database: ``Field.update_db_column`` returns
early when ``information_schema.columns.udt_name`` already equals the
field's ``column_type[0]``, and a ``vector(1024)`` column reports
``udt_name = 'vector'``. See ``models/fields_vector.py`` for the full note.

The HNSW index is still created with idempotent raw SQL in ``init()``:
indexes are not read through the ORM, and ``vector_cosine_ops`` is a
pgvector-specific operator class. The HNSW choice itself is deliberate —
IVFFlat builds faster but needs its ``lists`` count tuned to the corpus
size, while HNSW has no training step and stays fast as the corpus grows,
which is the right trade for a few thousand bills that only ever grows.

Queries (run by the RAG validation step, or by hand for the EXPLAIN
exercise in docs/vector-search.md):

```sql
SELECT partner_id, move_id, content,
       1 - (embedding <=> :query_vector) AS cosine_similarity
FROM invoice_agent_vendor_doc
ORDER BY embedding <=> :query_vector
LIMIT 10;
```

The HNSW index answers that ``ORDER BY ... <=>`` in O(log n) instead of a
full scan.
"""

import logging

from odoo import api, fields, models

from .fields_vector import Vector

_logger = logging.getLogger(__name__)

# Must match the service's voyage-3 dimension (app/embeddings.py).
EMBEDDING_DIMENSIONS = 1024


class InvoiceAgentVendorDoc(models.Model):
    _name = "invoice.agent.vendor.doc"
    _description = "Vendor/GL history RAG document (pgvector embedding)"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        index=True,
        ondelete="cascade",
        help="Vendor the bill belongs to (denormalized for filtered search).",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Posted Bill",
        index=True,
        ondelete="cascade",
        help="The posted vendor bill this document was rendered from. One "
        "document per posted bill — lines travel together with their GL "
        "codes (see account.move._build_rag_document).",
    )
    content = fields.Text(
        string="RAG Content",
        readonly=True,
        help="Compact text rendered by _build_rag_document(): partner name, "
        "invoice date, reference, then each line's name, GL code, quantity "
        "and subtotal.",
    )
    indexed_at = fields.Datetime(
        string="Indexed At",
        readonly=True,
        help="When the embedding was written (backfill or live post).",
    )
    # Declared to the ORM (see the module docstring and fields_vector.py):
    # the column is a real PostgreSQL vector(1024), created and reconciled by
    # _auto_init rather than by hand. Reading it through the ORM yields a
    # list[float]; the pgvector operators still apply in SQL.
    embedding = Vector(
        size=EMBEDDING_DIMENSIONS,
        string="Embedding",
        readonly=True,
        copy=False,
        help="1024-dim voyage-3 embedding of ``content``, stored as a real "
        "vector(1024) PostgreSQL column so pgvector's cosine operator "
        "(<=>) runs on it directly.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # New-style constraint (Odoo dropped _sql_constraints support): without
    # this UNIQUE(move_id), upsert_embedding()'s ON CONFLICT (move_id) has
    # no matching constraint and every embed upsert would fail.
    _move_id_unique = models.Constraint(
        "UNIQUE(move_id)",
        "One RAG document per posted bill — a redelivered embed job "
        "upserts, never duplicates.",
    )

    def _valid_field_parameter(self, field, name):
        """Accept the ``size`` parameter that the ``Vector`` field takes."""
        if name == "size":
            return True
        return super()._valid_field_parameter(field, name)

    # ------------------------------------------------------------------
    # schema bootstrap
    # ------------------------------------------------------------------
    def _auto_init(self):
        """Create the pgvector extension *before* the ORM adds the column.

        ``embedding`` is a declared field, so ``_auto_init`` will try to
        ``CREATE`` the ``vector(1024)`` column. On a database whose image
        does not preload pgvector that raises ``type "vector" does not
        exist``, and ``init()`` runs too late to help — so the extension is
        ensured here first. ``IF NOT EXISTS`` keeps it a no-op where the
        image's initdb hook already enabled it, and the db user is the
        superuser in both the compose setup (``POSTGRES_USER=odoo``) and CI.
        """
        self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
        return super()._auto_init()

    def init(self):
        """Create the HNSW cosine index idempotently.

        Only the index is bootstrapped here: the ``embedding`` column belongs
        to the declared ``Vector`` field, so ``_auto_init`` owns its DDL.
        """
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS
            invoice_agent_vendor_doc_embedding_hnsw_idx
            ON invoice_agent_vendor_doc
            USING hnsw (embedding vector_cosine_ops)
            """
        )
        _logger.info(
            "invoice_agent_vendor_doc: HNSW cosine index ensured on the "
            "declared vector(%d) column",
            EMBEDDING_DIMENSIONS,
        )

    # ------------------------------------------------------------------
    # upsert / search
    # ------------------------------------------------------------------
    @api.model
    def _to_pgvector(self, vector_values):
        """Render ``vector_values`` as the pgvector literal for a cast.

        The format is defined once, by the ``Vector`` field's
        ``convert_to_cache`` — previously it was re-derived by hand here and
        in :meth:`search_similar`.
        """
        return self._fields["embedding"].convert_to_cache(
            list(vector_values),
            self,
        )

    @api.model
    def upsert_embedding(self, move_id, content, vector_values):
        """Insert or replace the document for ``move_id`` with its embedding.

        Kept as a single ``INSERT ... ON CONFLICT`` so a redelivered embed
        job is one atomic statement rather than a search-then-write race.

        :param vector_values: list of 1024 floats from the voyage-3 embedder.
        """
        move = self.env["account.move"].browse(move_id).exists()
        partner_id = move.partner_id.id if move else False
        self.env.cr.execute(
            """
            INSERT INTO invoice_agent_vendor_doc
                (partner_id, move_id, content, embedding, indexed_at)
            VALUES (
                %s, %s, %s,
                %s::vector, now()
            )
            ON CONFLICT (move_id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                indexed_at = now()
            """,
            (
                partner_id,
                int(move_id),
                content or "",
                self._to_pgvector(vector_values),
            ),
        )
        return True

    @api.model
    def search_similar(self, query_vector, limit=10):
        """Cosine-similarity search over the HNSW index.

        The vector is passed as a bound parameter and cast with
        ``::vector``, so no query text is ever assembled from data.
        """
        self.env.cr.execute(
            """
            SELECT move_id, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM invoice_agent_vendor_doc
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (
                self._to_pgvector(query_vector),
                self._to_pgvector(query_vector),
                limit,
            ),
        )
        rows = self.env.cr.fetchall()
        if not rows:
            return self.env["account.move"]
        return self.env["account.move"].browse([row[0] for row in rows])
