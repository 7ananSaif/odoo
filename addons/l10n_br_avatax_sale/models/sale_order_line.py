# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    l10n_br_goods_operation_type_id = fields.Many2one(
        "l10n_br.operation.type",
        string="Override Operation Type",
        help="Brazil: If an Operation Type is selected, it will be applied to the product in the line, "
            "determining the CFOP for that line. If no selection is made, the operation type will be inherited from the header."
    )

    def _prepare_invoice_line(self, **optional_values):
        invoice_line = super()._prepare_invoice_line(**optional_values)
        invoice_line['l10n_br_goods_operation_type_id'] = self.l10n_br_goods_operation_type_id.id
        return invoice_line
