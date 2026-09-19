import logging

from odoo import fields, models

logger = logging.getLogger(__name__)


class AccountAvataxUniqueCode(models.AbstractModel):
    """Enables unique Avatax references. These are based on the database ID because
    they cannot change. They're made searchable so customers can easily cross-reference
    between Odoo and Avalara.
    """
    _name = 'account.avatax.unique.code'
    _description = 'Mixin to generate unique ids for Avatax'

    avatax_unique_code = fields.Char(
        "Avalara Code",
        compute="_compute_avatax_unique_code",
        search="_search_avatax_unique_code",
        store=False,
        help="Use this code to cross-reference in the Avalara portal."
    )

    def _compute_avatax_unique_code(self):
        for record in self:
            record.avatax_unique_code = '%s %s' % (record._description, record.id)

    def _search_avatax_unique_code(self, operator, value):
        if operator in ('like', 'ilike'):
            operator = 'in'
            value = [value]
        if operator != 'in':
            return NotImplemented

        # allow searching with or without prefix
        prefix = self._description.lower() + " "
        try:
            ids = [
                int(number_v)
                for v in value
                if v is not False  # ignore False value
                if (number_v := (v if not v.lower().startswith(prefix) else v[len(prefix):]))
                if number_v.isdigit()
            ]
        except AttributeError as e:
            raise ValueError("Invalid avatax_unique_code search value") from e
        return [('id', 'in', ids)]
