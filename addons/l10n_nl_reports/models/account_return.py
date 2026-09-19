from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_nl_reports.nl_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _get_pay_wizard(self):
        if self.type_id == self.env.ref('l10n_nl_reports.nl_tax_return_type'):
            vat_pay_wizard = self.env['l10n_nl_reports.vat.pay.wizard'].create({
                'company_id': self.company_id.id,
                'partner_bank_id': self.type_id.payment_partner_bank_id.id,
                'currency_id': self.amount_to_pay_currency_id.id,
                'amount_to_pay': self.total_amount_to_pay,
                'return_id': self.id,
            })

            return {
                'type': 'ir.actions.act_window',
                'name': self.env._("VAT Payment"),
                'res_model': 'l10n_nl_reports.vat.pay.wizard',
                'res_id': vat_pay_wizard.id,
                'views': [(False, 'form')],
                'target': 'new',
            }

        return super()._get_pay_wizard()

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # OVERRIDE
        """Handle corrective tax returns and rounding on the tax report for the Netherlands."""
        if self.type_external_id == 'l10n_nl_reports.nl_tax_correction_return_type':
            # Balance out the amounts of the previous closing entries for a correction.
            previous_closing_lines = self.env['account.move.line'].search([
                ('move_id.closing_return_id.company_id', '=', company.id),
                ('move_id.closing_return_id.date_from', '>=', options['date']['date_from']),
                ('move_id.closing_return_id.date_to', '<=', options['date']['date_to']),
                ('move_id.closing_return_id.type_id', 'in', (
                    self.env.ref('l10n_nl_reports.nl_tax_return_type').id,
                    self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id,
                )),
            ])
            results_account_ids = {r['account_id'] for r in results}

            balance_per_line = defaultdict(int)
            # Sum all amounts of the previous closings per account and tax name.
            for line in previous_closing_lines:
                if line.account_id.id in results_account_ids:
                    balance_per_line[line.account_id.id, line.name] += line.balance

            tax_group_id = None
            # Add the previously computed sums to the query results to balance them out.
            for result in results:
                # Keep the last tax group to add extra lines at the end.
                tax_group_id = result['tax_group_id']
                balance = balance_per_line[result['account_id'], result['tax_name']]
                if not company.currency_id.is_zero(balance):
                    result['amount'] += balance
                    balance_per_line.pop((result['account_id'], result['tax_name']))
            # Filter out lines amounting in zero.
            results = [result for result in results if not company.currency_id.is_zero(result['amount'])]

            # Process the remaining lines that could not be matched.
            for (account_id, name), balance in balance_per_line.items():
                if company.currency_id.is_zero(balance):
                    continue
                results.append({
                    'tax_name': name,
                    'amount': balance,
                    'tax_group_id': tax_group_id,
                    'account_id': account_id,
                })

        if self.type_external_id in ('l10n_nl_reports.nl_tax_return_type', 'l10n_nl_reports.nl_tax_correction_return_type'):
            # Apply the rounding from the Dutch tax report by adding a line to the end of the query results
            # representing the sum of the roundings on each line of the tax report.
            rounding_accounts = {
                'profit': company.l10n_nl_rounding_difference_profit_account_id,
                'loss': company.l10n_nl_rounding_difference_loss_account_id,
            }

            vat_results_summary = [
                ('total', self.env.ref('l10n_nl.tax_report_rub_btw_5g').id, 'tax'),
            ]

            return self._vat_closing_entry_results_rounding(company, options, results, rounding_accounts, vat_results_summary)

        return super()._postprocess_vat_closing_entry_results(company, options, results)

    def _get_closing_report_options(self):
        options = super()._get_closing_report_options()
        options['return_id'] = self.id

        if self.type_id.id == self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id:
            options['l10n_nl_is_correction'] = True

        return options
