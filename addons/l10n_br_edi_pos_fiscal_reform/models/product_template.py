# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_br_operation_type_pos_id = fields.Many2one(
        'l10n_br.operation.type',
        string='POS Operation Type',
        help='Brazil: if an Operation Type is selected, it will be added on Point of Sale orders.'
    )
