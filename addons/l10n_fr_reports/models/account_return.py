from odoo import _, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # OVERRIDE
        """ Apply the rounding from the French tax report by adding a line to the end of the query results
            representing the sum of the roundings on each line of the tax report.
        """
        if self.type_external_id == 'l10n_fr_reports.vat_return_type':
            rounding_accounts = {
                'profit': company.l10n_fr_rounding_difference_profit_account_id,
                'loss': company.l10n_fr_rounding_difference_loss_account_id,
            }

            vat_results_summary = [
                ('due', self.env.ref('l10n_fr_account.tax_report_32').id, 'balance'),
                ('due', self.env.ref('l10n_fr_account.tax_report_22').id, 'balance'),
                ('deductible', self.env.ref('l10n_fr_account.tax_report_27').id, 'balance'),
            ]
            return self._vat_closing_entry_results_rounding(company, options, results, rounding_accounts, vat_results_summary)

        return super()._postprocess_vat_closing_entry_results(company, options, results)

    def action_submit(self):
        # EXTENDS account_reports
        if self.type_external_id == 'l10n_fr_reports.vat_return_type':
            l10n_fr_vat_report = self.env['l10n_fr_reports.send.vat.report'].create({
                'report_id': self.type_id.report_id.id,
                'return_id': self.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
            })
            return l10n_fr_vat_report._get_records_action(name=_("EDI VAT"), target='new', res_id=l10n_fr_vat_report.id)

        return super().action_submit()

    def action_reset_tax_return_common(self):
        """ Extends of account report to remove the external value if we reset a submitted return.
            This external value is created when the locking move is created.
        """
        # EXTENDS account_reports
        self.ensure_one()
        if self.state == 'submitted' and self.company_id.account_fiscal_country_id.code == 'FR':
            external_values = self.env['account.report.external.value'].search([
                ('date', '=', self.date_to),
                ('target_report_expression_id', 'in', {
                    self.env.ref('l10n_fr_account.tax_report_26_external_tag', raise_if_not_found=False).id,
                    self.env.ref('l10n_fr_account.tax_report_22_applied_carryover', raise_if_not_found=False).id,
                }),
            ])
            external_values.unlink()

        return super().action_reset_tax_return_common()
