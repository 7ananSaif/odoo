# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _
from odoo.exceptions import UserError


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def action_payslip_done(self):
        unregistered_companies = self.company_id.filtered(lambda c: not c.l10n_au_bms_id and c.country_code == 'AU')
        if unregistered_companies:
            raise UserError(_("Please register your payroll before submitting the report. You can register it at\n"
                              "Configuration > Settings > Payroll > Australian Localization > Single Touch Payroll Register"))
        return super().action_payslip_done()

    def _add_payslip_to_superstream(self):
        if invalid_accounts := self.employee_id.l10n_au_super_account_ids.filtered(lambda x: x.account_active and x.fund_type == 'ARPA' and not x.fund_id.is_valid):
            raise UserError(_("The following employee(s) superannuation fund is not valid.\n%s", '\n'.join(invalid_accounts.employee_id.mapped('name'))))
        return super()._add_payslip_to_superstream()

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            # Force the cron to be enabled in case its disabled.
            'l10n_au_hr_payroll_api', [
                'data/ir_cron_data.xml',
            ])]
