# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends('sale_line_id.order_id.shopee_fulfillment_type')
    def _compute_reference(self):
        super()._compute_reference()
        for record in self:
            if record.sale_line_id and record.sale_line_id.order_id.shopee_fulfillment_type == 'fbs':
                record.reference = _('Shopee move: %s', record.reference)
