# Adapted from Odoo 19's ``addons/ai/orm/field_vector.py`` (OEEL-1).
"""A ``pgvector`` column type for the ORM.

Odoo 19 ships a ``Vector`` field in the ``ai`` addon
(``addons/ai/orm/field_vector.py``), and that is the type
``invoice.agent.vendor.doc.embedding`` should be declared with. That addon is
present in this checkout, but **it is not depended on, deliberately**:

* ``addons/ai/__manifest__.py`` declares ``'license': 'OEEL-1'`` — it is an
  Odoo **Enterprise** module. Making this custom addon depend on it would
  make the custom addon a derivative of Enterprise-licensed code.
* ``ai`` also carries a ``pre_init_hook``, view/asset patches for
  ``mail`` and its own cron and demo data, so depending on it would install
  all of that on every database where ``invoice_agent`` is installed — for
  the sake of one field type.

The class is therefore adapted from that file (≈30 lines) rather than
imported. This is the option §4-P2-3 of the review records as the fallback;
the substance — the column being *declared to the ORM* instead of created by
hand — is what matters, not where the class lives. If this deployment ever
takes an Enterprise licence and depends on ``ai``, delete this file and
import ``ai``'s ``Vector`` instead.

**Why declaring the column matters.** With the column created by a raw
``ALTER TABLE ... ADD COLUMN`` in ``init()``, the field was invisible to the
ORM, so the model got none of:

* ``_auto_init`` schema reconciliation on every upgrade,
* ORM-level reading/writing of the column,
* drift detection between the code and the database.

**Declaring it is non-destructive on an existing database.** When the column
already exists, ``Field.update_db_column`` returns early as soon as
``information_schema.columns.udt_name`` equals ``column_type[0]`` — see
``odoo/orm/fields.py``::

    if column['udt_name'] == self.column_type[0]:
        return

A ``vector(1024)`` column already reports ``udt_name = 'vector'``, which is
exactly ``column_type[0]`` here, so no ``ALTER COLUMN ... TYPE`` statement is
issued and no data is rewritten.
"""

import json

from odoo import fields


def pg_vector(size):
    """Return the PostgreSQL type name for a ``pgvector`` column."""
    if not isinstance(size, int):
        msg = f"vector size should be an int, got {size!r}"
        raise TypeError(msg)
    if size > 0:
        return "vector(%d)" % size
    return "vector"


class Vector(fields.Field):
    """A ``pgvector`` embedding column stored as the ``vector(n)`` PG type.

    Because the column really is ``vector(n)``, the pgvector operators work
    directly in SQL — ``<=>`` (cosine distance), ``<#>`` (negative inner
    product) and ``<->`` (L2 distance) — without a cast dance or a detour
    through ``jsonb``.

    Values are ``list[float]`` at the ORM boundary. The database literal is
    produced by ``str()``: ``[0.1, 0.2]`` is the syntax pgvector's input
    function parses, and it is what ``convert_to_cache`` returns.
    """

    type = "vector"
    size = None

    def _setup_attrs__(self, model_class, name):
        super()._setup_attrs__(model_class, name)
        assert self.size is None or isinstance(self.size, int), (
            "Vector field %s with non-integer size %r" % (self, self.size)
        )

    @property
    def _column_type(self):
        """Return ``(udt_name, full_type)``; the tuple Odoo expects."""
        return ("vector", pg_vector(self.size))

    def convert_to_cache(self, value, record, validate=True):
        """Return the pgvector literal for ``value`` (or ``None``)."""
        if value is None or value is False:
            return None
        return str(value)

    def convert_to_record(self, value, record):
        """Return the stored literal as a ``list[float]``."""
        return False if value is None else json.loads(value)
