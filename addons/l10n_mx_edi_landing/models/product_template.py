from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_mx_edi_use_customs_invoicing = fields.Boolean(
        company_dependent=True,
        help="""If enabled, customs numbers will be set automatically when creating an invoice line from a sale line.
                An invoice line will be created for each customs. Toggling this option will affect future created sale lines.
            """,
        tracking=True,
    )
    l10n_mx_edi_can_use_customs_invoicing = fields.Boolean(
        string='Customs invoicing',
        compute="_compute_l10n_mx_edi_can_use_customs_invoicing",
        inverse="_inverse_l10n_mx_edi_can_use_customs_invoicing",
    )

    @api.depends('invoice_policy', 'tracking', 'lot_valuated', 'company_id')
    @api.depends_context('company')
    def _compute_l10n_mx_edi_can_use_customs_invoicing(self):
        for product in self:
            product.l10n_mx_edi_can_use_customs_invoicing = (
                product.invoice_policy == 'delivery'
                and product.tracking != 'none'
                and product.lot_valuated
                and product.l10n_mx_edi_use_customs_invoicing
            )

    def _inverse_l10n_mx_edi_can_use_customs_invoicing(self):
        for product in self:
            product.l10n_mx_edi_use_customs_invoicing = product.l10n_mx_edi_can_use_customs_invoicing

    @api.constrains('l10n_mx_edi_use_customs_invoicing', 'l10n_mx_edi_can_use_customs_invoicing')
    def _check_l10n_mx_edi_use_customs_invoicing(self):
        for product in self:
            if product.l10n_mx_edi_use_customs_invoicing and not product.l10n_mx_edi_can_use_customs_invoicing:
                raise ValidationError(_(
                    "Automatic computation of customs numbers is only allowed for products tracked\n"
                    "by lot/sn with valuation and invoiced by qty delivered."
                ))
