# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Add a compute to change the default.
    l10n_br_goods_operation_type_id = fields.Many2one(
        compute='_compute_l10n_br_goods_operation_type_id',
        store=True,
        readonly=False,
    )

    @api.depends('product_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        website_order_lines = self.filtered('order_id.website_id')
        for line in website_order_lines:
            line.l10n_br_goods_operation_type_id = line.product_id.l10n_br_operation_type_ecommerce_id

        super(SaleOrderLine, self - website_order_lines)._compute_l10n_br_goods_operation_type_id()
