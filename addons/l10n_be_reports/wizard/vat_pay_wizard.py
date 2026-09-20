# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10n_Be_ReportsVatPayWizard(models.TransientModel):
    _name = 'l10n_be_reports.vat.pay.wizard'
    _inherit = ['qr.code.payment.wizard']
    _description = "Payment instructions for VAT"

    def _generate_communication(self):
        return self._be_company_vat_communication(self.company_id)

    def action_send_email_instructions(self):
        self.ensure_one()
        template = self.env.ref('l10n_be_reports.email_template_vat_payment_instructions', raise_if_not_found=False)
        return self.return_id.action_send_email_instructions(self, template)

    def action_mark_as_paid(self):
        # EXTENDS account.return.payment.wizard
        action = super().action_mark_as_paid()
        for line in self.return_id.closing_move_ids.line_ids:
            if line.account_id == self.partner_id.property_account_payable_id:
                # Partner added to move line for auto reconciliation
                line.partner_id = self.partner_id
        return action
