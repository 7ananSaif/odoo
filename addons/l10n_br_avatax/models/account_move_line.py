# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_br_goods_operation_type_id = fields.Many2one(
        "l10n_br.operation.type",
        copy=False,
        string="Override Operation Type",
        help="Brazil: If an Operation Type is selected, it will be applied to the product in the line, "
            "determining the CFOP for that line. If no selection is made, the operation type will be inherited from the header."
    )
