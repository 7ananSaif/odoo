from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ae_tax_report_liabilities_account = fields.Many2one(
        comodel_name='account.account',
        related='company_id.l10n_ae_tax_report_liabilities_account',
        string="Liability Account",
        readonly=False,
    )
    l10n_ae_tax_report_expenses_account = fields.Many2one(
        comodel_name='account.account',
        related='company_id.l10n_ae_tax_report_expenses_account',
        readonly=False,
    )
    l10n_ae_tax_report_asset_account = fields.Many2one(
        comodel_name='account.account',
        related='company_id.l10n_ae_tax_report_asset_account',
        string="Asset Account",
        readonly=False,
    )
