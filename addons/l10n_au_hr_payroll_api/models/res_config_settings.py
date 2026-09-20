# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_au_payroll_mode = fields.Selection(
        related="company_id.l10n_au_payroll_mode",
        string="Payroll Mode",
        readonly=False,
        required=True
    )
    l10n_au_registration_status = fields.Selection(
        related="company_id.l10n_au_registration_status",
        string="Registration Status"
    )

    def register_payroll(self):
        self.company_id.register_payroll()

    def action_view_payroll_onboarding(self):
        return self.company_id.action_view_payroll_onboarding()

    def cancel_ongoing_registration(self):
        self.company_id.l10n_au_employer_registration_ids.filtered(lambda x: x.status == 'pending').sudo().unlink()
