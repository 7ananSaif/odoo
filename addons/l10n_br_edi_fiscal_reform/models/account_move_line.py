# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_br_cbs_ibs_deduction = fields.Monetary(
        string='CBS/IBS Credit',
        currency_field='currency_id',
        help='Brazil: Deduction value to reduce the CBS/IBS taxable base in outbound invoices for certain operations.',
    )

    # Add a compute to change the default.
    l10n_br_goods_operation_type_id = fields.Many2one(
        compute='_compute_l10n_br_goods_operation_type_id',
        store=True,
        readonly=False,
    )

    @api.depends('product_id')
    def _compute_l10n_br_goods_operation_type_id(self):
        for line in self:
            move_id = line.move_id

            if move_id.is_sale_document() and (operation_type := line.product_id.l10n_br_operation_type_sales_id) or \
               move_id.is_purchase_document() and (operation_type := line.product_id.l10n_br_operation_type_purchases_id):
                line.l10n_br_goods_operation_type_id = operation_type
