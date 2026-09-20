from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ae_tax_report_liabilities_account = fields.Many2one(comodel_name='account.account')
    l10n_ae_tax_report_expenses_account = fields.Many2one(comodel_name='account.account')
    l10n_ae_tax_report_asset_account = fields.Many2one(comodel_name='account.account')
