from odoo import fields, models, _


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _check_suite_annual_closing(self, check_codes_to_ignore):
        checks = super()._check_suite_annual_closing(check_codes_to_ignore)

        if 'check_loans' not in check_codes_to_ignore:
            domain = [
                ('company_id', 'in', self.company_ids.ids),
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
            ]
            loans_exist = self.env['account.loan'].sudo().search_count(domain)
            if not loans_exist:
                checks.append({
                    'name': _("Loans"),
                    'message': _("Odoo manages your amortizations automatically. No loans were found for this period. Ensure your loans are properly registered for automatic amortizations calculation."),
                    'code': 'check_loans',
                    'result': 'todo',
                })
        return checks
