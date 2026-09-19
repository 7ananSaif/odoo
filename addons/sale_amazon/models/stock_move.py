# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends('sale_line_id.order_id.amazon_channel')
    def _compute_reference(self):
        super()._compute_reference()
        for record in self:
            if record.sale_line_id and record.sale_line_id.order_id.amazon_channel == 'fba':
                record.reference = _('Amazon move: %s', record.reference)
