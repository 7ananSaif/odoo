from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # OVERRIDE 'account_reports'
        """ Apply the rounding from the Estonian tax report to account for rounding differences between line-level
        tax calculations and the Estonian government's total tax computation (base_amount * tax_rate).
        """
        if self.type_external_id == 'l10n_ee_reports.ee_tax_return_type':
            rounding_accounts = {
                'profit': company.l10n_ee_rounding_difference_profit_account_id,
                'loss': company.l10n_ee_rounding_difference_loss_account_id,
            }

            vat_results_summary = [
                ('due', self.env.ref('l10n_ee.tax_report_line_12').id, 'balance'),
                ('deductible', self.env.ref('l10n_ee.tax_report_line_13').id, 'balance'),
            ]

            return self._vat_closing_entry_results_rounding(company, options, results, rounding_accounts, vat_results_summary)

        return super()._postprocess_vat_closing_entry_results(company, options, results)

    def action_submit(self):
        # Extends account_reports
        if self.type_external_id == "l10n_ee_reports.ee_tax_return_type":
            return self.env["l10n_ee_reports.tax.return.submission.wizard"]._open_submission_wizard(self)
        if self.type_external_id == "l10n_ee_reports.ee_ec_sales_list_return_type":
            return self.env["l10n_ee_reports.ec.sales.list.submission.wizard"]._open_submission_wizard(self)
        if self.type_external_id == "l10n_ee_reports.ee_kmd_inf_tax_return_type":
            return self.env["l10n_ee_reports.kmd.inf.return.submission.wizard"]._open_submission_wizard(self)

        return super().action_submit()
