from odoo import fields, models, _
from odoo.tools.misc import format_date
import datetime

from copy import deepcopy


class L10nRoTrialBalance5ColumnReportHandler(models.AbstractModel):
    _name = 'l10n.ro.trial.balance.5.column.report.handler'
    _inherit = 'account.trial.balance.report.handler'
    _description = "Romanian Trial Balance Report (5 Columns)"

    def _custom_options_initializer(self, report, options, previous_options):

        if self._show_start_of_year_column(options):
            self._generate_start_of_year_columns(report, options)

        super()._custom_options_initializer(report, options, previous_options)

        self._generate_total_amounts_columns(options)

    def _show_start_of_year_column(self, options):
        options_date_from = fields.Date.from_string(options['date']['date_from'])
        return options_date_from.month != 1 or options_date_from.day != 1

    def _generate_start_of_year_columns(self, report, options):
        # Get date range
        date_from = self.env.company.compute_fiscalyear_dates(
            fields.Date.from_string(options['date']['date_to'])
        )['date_from']

        date_to = fields.Date.from_string(
            min(key['forced_options']['date']['date_from']
                for key in options['column_groups'].values())
        ) - datetime.timedelta(days=1)

        # Format dates and create header name
        date_from_str = fields.Date.to_string(date_from)
        date_to_str = fields.Date.to_string(date_to)

        month_from, year_from = format_date(self.env, date_from_str, date_format="MMM YYYY").split()
        month_to, year_to = format_date(self.env, date_to_str, date_format="MMM YYYY").split()

        header_name = (
            f"{month_from} {year_from} - {month_to} {year_to}" if year_from != year_to
            else f"{month_from} - {month_to} {year_from}" if month_from != month_to
            else f"{month_from} {year_from}"
        )

        # Create column values
        column_header_values = {
            'forced_options': {
                'date': {
                    'string': header_name,
                    'period_type': 'custom',
                    'currency_table_period_key': f"{date_from_str}_{date_to_str}",
                    'mode': 'range',
                    'date_from': date_from_str,
                    'date_to': date_to_str
                }
            }
        }

        # Generate new columns
        column_headers = [[{'name': header_name, **column_header_values}], *options['column_headers'][1:]]
        new_column_group_vals = report._generate_columns_group_vals_recursively(
            column_headers,
            {'horizontal_groupby_element': {}, **column_header_values}
        )

        new_columns, new_column_groups = report._build_columns_from_column_group_vals(
            column_header_values['forced_options'],
            new_column_group_vals
        )

        options['columns'] = new_columns + options['columns']
        options['column_headers'][0] = [{'name': header_name, **column_header_values}, *options['column_headers'][0]]
        options['column_groups'].update(new_column_groups)

    def _generate_total_amounts_columns(self, options):
        end_balance_columns = deepcopy(options['columns'][-2:])
        end_balance_column_header = deepcopy(options['column_headers'][0][-1])

        options['columns'].extend(end_balance_columns)
        options['column_headers'][0].append(end_balance_column_header)
        options['column_headers'][0][-2]['name'] = _("Total Amount")

    def _display_single_column_for_initial_and_end_sections(self, options):
        # Override
        return False

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)

        end_balance_debit_index = -2
        end_balance_credit_index = -1
        total_debit = 0.0
        total_credit = 0.0

        for line in lines:
            balance = line['columns'][end_balance_debit_index]['no_format'] - line['columns'][end_balance_credit_index]['no_format']
            debit = max(balance, 0.0) or 0.0
            credit = max(-balance, 0.0) or 0.0
            line['columns'][end_balance_debit_index]['no_format'] = debit
            line['columns'][end_balance_credit_index]['no_format'] = credit
            total_debit += debit
            total_credit += credit

        lines[-1]['columns'][end_balance_debit_index]['no_format'] = self.env.company.currency_id.round(total_debit)
        lines[-1]['columns'][end_balance_credit_index]['no_format'] = self.env.company.currency_id.round(total_credit)

        return lines


class L10nRoTrialBalance4ColumnReportHandler(models.AbstractModel):
    _name = 'l10n.ro.trial.balance.4.column.report.handler'
    _inherit = 'l10n.ro.trial.balance.5.column.report.handler'
    _description = "Romanian Trial Balance Report (4 Columns)"

    def _show_start_of_year_column(self, options):
        # Override
        return False
