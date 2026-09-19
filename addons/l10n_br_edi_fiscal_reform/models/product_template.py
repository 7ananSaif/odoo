# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_br_nbs_id = fields.Many2one(
        'l10n_br.nbs.code',
        'NBS Code',
        help='Brazil: Brazilian Service Classification (NBS) code required for services in the tax reform.'
    )
    l10n_br_legal_uom_id = fields.Many2one(
        'uom.uom',
        'Legal Unit of Measure',
        help='Brazil: Determines the conversion factor between the commercial unit and the taxable unit when taxes apply per quantity (ad rem).',
    )
    l10n_br_taxable_is = fields.Boolean(
        'IS taxable',
        default=True,
        help='Brazil: Indicates that this product is exempt from the Selective Tax (IS) due to a specific fiscal benefit, overriding the standard IS taxation rules.',
    )
    l10n_br_operation_type_sales_id = fields.Many2one(
        'l10n_br.operation.type',
        string='Sales Operation Type',
        help='Brazil: if an Operation Type is selected, it will be added on sale orders and invoices. If empty, it won’t be added on the line, '
             'and the one on the header will be used.'
    )
    l10n_br_operation_type_purchases_id = fields.Many2one(
        'l10n_br.operation.type',
        string='Purchases Operation Type',
        help='Brazil: if an Operation Type is selected, it will be added on the vendor bill. If empty, it won’t be added on the line, '
             'and the one on the header will be used.'
    )
