from odoo import models, Command
from odoo.tools.translate import _
from odoo.exceptions import RedirectWarning


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _proceed_with_locking(self, options_to_inject=None):
        # EXTEND: account_reports account.return
        if self.type_id.report_id == self.env.ref('l10n_ae_reports.ae_corporate_tax_report'):
            options = {**self._get_closing_report_options(), **(options_to_inject or {})}
            self._generate_tax_closing_entries(options)

        return super()._proceed_with_locking(options_to_inject)

    def _create_accounting_entry(self, date_period, value, company, debit_account, credit_account):
        return self.env['account.move'].create({
            'ref': _("Corporate Tax (9%%) Recognition Entry for %(date_period)s", date_period=date_period['string']),
            'closing_return_id': self.id,
            'journal_id': company._get_tax_closing_journal().id,
            'company_id': company.id,
            'line_ids': [
                Command.create({
                    'account_id': debit_account.id,
                    'debit': value,
                }),
                Command.create({
                    'account_id': credit_account.id,
                    'credit': value,
                })
            ]
        })

    def _get_report_total_amount(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        total_amount_line = self.env.ref('l10n_ae_reports.ae_corporate_tax_report_line_total_income')
        # Safely take the first key from the column_groups dict because there is only 1 element in the dict
        column_group_key = next(column_group_key for column_group_key in options['column_groups'])

        totals = report._compute_expression_totals_for_each_column_group(report.line_ids.expression_ids, options)
        total_amount_line_expr = total_amount_line.expression_ids[0]
        balance_col = totals[column_group_key]
        return next(v for k, v in balance_col.items() if k == total_amount_line_expr)['value']

    def _generate_tax_closing_entries(self, options):
        # EXTEND: account_reports account.return
        """
        Generates and compute a closing move for every companies of the return.
        :param options: report options
        :return: The closing moves.
        """
        if self.company_id.country_id.code != 'AE' or self.type_id.report_id != self.env.ref('l10n_ae_reports.ae_corporate_tax_report', raise_if_not_found=False):
            return super()._generate_tax_closing_entries(options)
        expenses_account = self.company_id.l10n_ae_tax_report_expenses_account
        liabilities_account = self.company_id.l10n_ae_tax_report_liabilities_account
        assets_account = self.company_id.l10n_ae_tax_report_asset_account

        options['export_mode'] = 'file'

        total_amount = self._get_report_total_amount(options)

        action = self.env.ref('account.action_account_config')

        if total_amount < 0:
            if not assets_account or not expenses_account:
                raise RedirectWarning(
                    message=_("The Asset Account or Expense Account is missing. Please check the setup from the settings and try again."),
                    action=action.id,
                    button_text=_("Go to Accounting Settings"),
                )
            move = self._create_accounting_entry(options['date'], total_amount, self.company_id, expenses_account, assets_account)
        else:
            if not expenses_account or not liabilities_account:
                raise RedirectWarning(
                    message=_("The Liability Account or Expense Account is missing. Please check the setup from the settings and try again."),
                    action=action.id,
                    button_text=_("Go to Accounting Settings"),
                )
            # see documentation for more details: https://tax.gov.ae/DataFolder/Files/Pdf/2024/Determination%20of%20Taxable%20Income%20-%2031%2007%202024.pdf
            threshold_amount = 375000
            tax_percentage = 9
            tax_amount = 0
            if total_amount > threshold_amount:
                tax_amount = (total_amount - threshold_amount) * tax_percentage / 100
            move = self._create_accounting_entry(options['date'], tax_amount, self.company_id, expenses_account, liabilities_account)
        move.action_post()

    def _get_tax_closing_payable_and_receivable_accounts(self):
        # EXTEND: account_reports account.return
        if self.type_external_id == 'l10n_ae_reports.ae_corporate_tax_return_type':
            liabilities_account = self.company_id.l10n_ae_tax_report_liabilities_account
            assets_account = self.company_id.l10n_ae_tax_report_asset_account
            return liabilities_account, assets_account
        return super()._get_tax_closing_payable_and_receivable_accounts()
