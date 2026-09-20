from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_can_use_customs_invoicing = fields.Boolean(compute="_compute_l10n_mx_edi_can_use_customs_invoicing")

    @api.depends('sale_line_ids')
    def _compute_l10n_mx_edi_can_use_customs_invoicing(self):
        for aml in self:
            aml.l10n_mx_edi_can_use_customs_invoicing = aml.sale_line_ids[:1].l10n_mx_edi_can_use_customs_invoicing
