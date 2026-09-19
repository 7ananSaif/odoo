# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools import SQL


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def _get_extra_query_base_tax_line_mapping(self) -> SQL:
        """Override to add vehicle_id matching condition for tax details query.
        This ensures that tax lines are only matched with base lines that have the same vehicle_id,
        preventing tax lines from being incorrectly merged when different vehicles are used.
        """
        query = super()._get_extra_query_base_tax_line_mapping()
        return SQL("%s AND COALESCE(base_line.vehicle_id, 0) = COALESCE(account_move_line.vehicle_id, 0)", query)
