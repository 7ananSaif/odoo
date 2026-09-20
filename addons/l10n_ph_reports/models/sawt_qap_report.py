# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import _, fields, models
from odoo.tools import date_utils, html2plaintext
from odoo.tools.misc import format_date
from odoo.tools.sql import SQL


class L10n_PhSawt_QapReportHandler(models.AbstractModel):
    _name = 'l10n_ph.sawt_qap.report.handler'
    _inherit = ['l10n_ph.generic.report.handler', 'account.tax.report.handler']
    _description = 'Withholding Taxes Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.setdefault('buttons', []).append(
            {
                'name': _('Export SAWT & QAP'),
                'sequence': 5,
                'action': 'print_report_to_dat',
                'file_export_type': _('DAT'),
            }
        )

    # First level, month rows
    def _build_month_lines(self, report, options):
        """ Fetches the months for which we have entries *that have tax grids* and build a report line for each of them. """
        month_lines = []
        queries = []

        # 1) Build the queries to get the months
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = self._get_report_query(report, column_group_options)
            # The joins are there to filter out months for which we would not have any lines in the report.
            queries.append(SQL(
                """
                  SELECT (date_trunc('month', account_move_line.date::date) + interval '1 month' - interval '1 day')::date AS taxable_month,
                         %(column_group_key)s                                                                              AS column_group_key
                    FROM %(table_references)s
                   WHERE %(search_condition)s AND account_tax.l10n_ph_atc IS NOT NULL
                GROUP BY taxable_month
                ORDER BY taxable_month DESC
                """,
                column_group_key=column_group_key,
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))

        # 2) Make the lines
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        for res in self.env.execute_query_dict(SQL(" UNION ALL ").join(queries)):
            line_id = report._get_generic_line_id('', '', markup=str(res['taxable_month']))
            month_lines.append({
                'id': line_id,
                'name': format_date(self.env, res['taxable_month'], date_format='MMMM y'),
                'unfoldable': True,
                'unfolded': line_id in options['unfolded_lines'] or unfold_all,
                'columns': [report._build_column_dict(None, _column) for _column in options['columns']],
                'level': 0,
                'expand_function': '_report_expand_unfoldable_line_l10n_ph_expand_month',
            })

        return month_lines

    def _report_expand_unfoldable_line_l10n_ph_expand_month(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        """ Used to expand a month line and load the second level, being the partner lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._get_markup(line_dict_id)
        partner_lines_values = self._query_partners(report, options, month, offset)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, progress, partner_lines_values,
                                                             report_line_method=self._get_report_line_partner)

    def _query_partners(self, report, options, month, offset):
        """ Query the values for the partner lines.
        The partner lines will sum up the values for the different columns while only being filtered for the given month.
        """
        limit = report.load_more_limit + 1 if report.load_more_limit and options['export_mode'] != 'print' else None
        end_date = fields.Date.from_string(month)  # Month is already set to the last day of the month.
        start_date = date_utils.start_of(end_date, 'month')
        queries = []

        extra_domain = [
            # Make sure to only fetch records that are in the parent's row month
            ('date', '>=', start_date),
            ('date', '<=', end_date),
        ]
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = self._get_report_query(report, column_group_options, extra_domain=extra_domain)
            tail_query = report._get_engine_query_tail(offset, limit)
            # Note about the lateral join; we use it because we actually only care about the fact that there is any tax_ids on the line and not which ones.
            # This allows us to get that line in the result a single time for it's amount (used as base amount); while the tax details will come from the join using tax_line_id.
            queries.append(SQL(
                """
                  SELECT %(column_group_key)s                                                                               AS column_group_key,
                         p.vat                                                                                              AS partner_vat,
                         COALESCE(
                             NULLIF(TRIM(CONCAT_WS(' ', p.last_name, p.first_name, p.middle_name)), ''),
                             p.name
                         )                                                                                                  AS register_name,
                         p.id                                                                                               AS partner_id,
                         COALESCE(
                             NULLIF(TRIM(CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)), ''),
                             p.name
                         )                                                                                                  AS partner_name,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                                  AS balance
                    FROM %(table_references)s
                    JOIN res_partner p ON p.id = account_move_line__move_id.commercial_partner_id
                    %(currency_table_join)s
                   WHERE %(search_condition)s
                GROUP BY p.id, %(account_tag_name)s
                ORDER BY p.id
                %(tail_query)s
                """,
                balance_select=report._currency_table_apply_rate(SQL('account_move_line.balance')),
                currency_table_join=report._currency_table_aml_join(options),
                column_group_key=column_group_key,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tail_query=tail_query,
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        return self._process_partner_lines(results, options)

    def _process_partner_lines(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        # We get the partners to get the correctly formatted address as we don't have by default in the db.
        partners = self.env["res.partner"].browse({values["partner_id"] for values in data_dict})
        partner_addresses = {
            partner.id: partner._display_address(without_company=True).replace('\n\n', '\n').replace('\n', ', ')  # Looks better in the Odoo view
            for partner in partners
        }
        for values in data_dict:
            # Initialise the move values
            if values['partner_id'] not in lines_values:
                lines_values[values['partner_id']] = {
                    'name': values['partner_name'],
                    'register_name': values['register_name'],
                    values['column_group_key']: {
                        'column_group_key': values['column_group_key'],
                        'partner_vat': values['partner_vat'],
                        'register_name': values['register_name'],
                        'partner_address': partner_addresses[values['partner_id']],
                    }
                }
            self._eval_report_grids_map(options, values, column_values=lines_values[values['partner_id']][values['column_group_key']])

        return self._filter_lines_with_values(options, lines_values)

    def _get_report_line_partner(self, report, options, partner_id, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        month = report._get_markup(parent_line_id)
        line_columns = self._get_line_columns(report, options, line_values)
        # Set the markup with the month, we can reuse it to filter the detailed move lines
        line_id = report._get_generic_line_id('res.partner', partner_id, markup=month, parent_line_id=parent_line_id)
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': line_values['name'] or line_values['register_name'],
            'unfoldable': True,
            'unfolded': line_id in options['unfolded_lines'] or unfold_all,
            'columns': line_columns,
            'level': 1,
            'caret_options': 'res.partner',
            'expand_function': '_report_expand_unfoldable_line_l10n_ph_expand_partner',
        }

    def _report_expand_unfoldable_line_l10n_ph_expand_partner(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        """ Used to expand a partner line and load the third level, being the account move lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._get_markup(line_dict_id)
        partner_id = report._get_res_id_from_line_id(line_dict_id, 'res.partner')
        lines_values = self._query_atc_lines(report, options, partner_id, month, offset)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, progress, lines_values,
                                                             report_line_method=self._get_report_line_atc)

    def _query_moves(self, report, options, partner_id, tax_id, month, offset):
        """ Query the values for the partner line.
        The move line will sum up the values for the different columns, while being filtered for the given month only.
        """
        limit = report.load_more_limit + 1 if report.load_more_limit and options['export_mode'] != 'print' else None
        end_date = fields.Date.from_string(month)
        start_date = date_utils.start_of(end_date, 'month')
        queries = []

        extra_domain = [
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('move_id.commercial_partner_id', '=', partner_id),
        ]
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = self._get_report_query(report, column_group_options, extra_domain=extra_domain)
            tail_query = report._get_engine_query_tail(offset, limit)
            queries.append(SQL(
                """
                  SELECT %(column_group_key)s                                                                               AS column_group_key,
                         account_move_line__move_id.id                                                                      AS move_id,
                         account_move_line__move_id.name                                                                    AS move_name,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                                  AS balance
                    FROM %(table_references)s
                    JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
                    %(currency_table_join)s
                    WHERE %(search_condition)s
                      AND %(tax_clause)s
                GROUP BY account_move_line__move_id.id, %(account_tag_name)s
                ORDER BY account_move_line__move_id.id
                %(tail_query)s
                """,
                balance_select=report._currency_table_apply_rate(SQL('account_move_line.balance')),
                column_group_key=column_group_key,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                currency_table_join=report._currency_table_aml_join(options),
                tax_clause=SQL('account_tax.id = %s', tax_id),
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tail_query=tail_query,
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        return self._process_moves(results, options)

    def _process_moves(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            if values['move_id'] not in lines_values:
                lines_values[values['move_id']] = {
                    'name': values['move_name'],
                    values['column_group_key']: {
                        'column_group_key': values['column_group_key'],
                        'move_id': values['move_id'],
                        'move_name': values['move_name'],
                    }
                }
            self._eval_report_grids_map(options, values, column_values=lines_values[values['move_id']][values['column_group_key']])
        return self._filter_lines_with_values(options, lines_values)

    def _get_report_line_move(self, report, options, move_id, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        line_columns = self._get_line_columns(report, options, line_values)
        line_id = report._get_generic_line_id('account.move', move_id, parent_line_id=parent_line_id)
        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': line_values['name'],
            'unfoldable': False,
            'unfolded': False,
            'columns': line_columns,
            'level': 3,
            'caret_options': 'account.move',
        }

    def _query_atc_lines(self, report, options, partner_id, month, offset):
        """ Query the values for the partner line.
        The move line will sum up the values for the different columns, while being filtered for the given move id only.
        """
        limit = report.load_more_limit + 1 if report.load_more_limit and options['export_mode'] != 'print' else None
        end_date = fields.Date.from_string(month)
        start_date = date_utils.start_of(end_date, 'month')
        queries = []

        extra_domain = [
            # Make sure to only fetch records that are in the parent's row month
            ('move_id.commercial_partner_id', '=', partner_id),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
        ]
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = self._get_report_query(report, column_group_options, extra_domain=extra_domain)
            tail_query = report._get_engine_query_tail(offset, limit)
            # Note, the multiplication per tax amount sign is there to show positive value for negative withholding taxes.
            queries.append(SQL(
                """
                  SELECT %(column_group_key)s                                                                               AS column_group_key,
                         account_tax.id                                                                                     AS tax_id,
                         account_tax.l10n_ph_atc                                                                            AS atc,
                         REGEXP_REPLACE(%(account_tax_description)s, '(<([^>]+)>)', '', 'g')                                AS tax_description,
                         ABS(account_tax.amount)                                                                            AS tax_rate,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                                  AS balance
                    FROM %(table_references)s
                    JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
                    %(currency_table_join)s
                   WHERE %(search_condition)s AND account_tax.l10n_ph_atc IS NOT NULL
                GROUP BY account_tax.l10n_ph_atc, account_tax.id, %(account_tag_name)s
                ORDER BY account_tax.id
                %(tail_query)s
                """,
                balance_select=report._currency_table_apply_rate(SQL('account_move_line.balance')),
                column_group_key=column_group_key,
                account_tax_description=self.env['account.tax']._field_to_sql('account_tax', 'description', query),
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                currency_table_join=report._currency_table_aml_join(options),
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tail_query=tail_query,
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        return self._process_atc_lines(results, options)

    def _process_atc_lines(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            if values['tax_id'] not in lines_values:
                lines_values[values['tax_id']] = {
                    'name': values['tax_description'],
                    values['column_group_key']: {
                        'column_group_key': values['column_group_key'],
                        'atc': values['atc'],
                        'tax_rate': values['tax_rate'],
                    }
                }
            self._eval_report_grids_map(options, values, column_values=lines_values[values['tax_id']][values['column_group_key']])
        return lines_values

    def _get_report_line_atc(self, report, options, tax_id, line_values, parent_line_id):
        """ Format the given values to match the report line format. """
        month = report._get_markup(parent_line_id)
        line_columns = self._get_line_columns(report, options, line_values)
        line_id = report._get_generic_line_id('account.tax', tax_id, markup=month, parent_line_id=parent_line_id)
        unfold_all = options['export_mode'] == 'print' or options.get('unfold_all')
        return {
            'id': line_id,
            'parent_id': parent_line_id,
            'name': line_values['name'],
            'unfoldable': True,
            'unfolded': line_id in options['unfolded_lines'] or unfold_all,
            'columns': line_columns,
            'level': 2,
            'caret_options': 'account.tax',
            'expand_function': '_report_expand_unfoldable_line_l10n_ph_expand_atc',
        }

    def _report_expand_unfoldable_line_l10n_ph_expand_atc(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        """ Used to expand an account move line and load the third level, being the tax lines. """
        report = self.env['account.report'].browse(options['report_id'])
        month = report._get_markup(line_dict_id)
        tax_id = report._get_res_id_from_line_id(line_dict_id, 'account.tax')
        partner_id = report._get_res_id_from_line_id(line_dict_id, 'res.partner')
        lines_values = self._query_moves(report, options, partner_id, tax_id, month, offset)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, progress, lines_values,
                                                             report_line_method=self._get_report_line_move)

    # ================
    # .DAT file export
    # ================

    def _get_dat_line_grouping_keys(self):
        return ['payee_id', 'tax_id']

    def _get_schedule_number(self, form_type_code, tags):
        """ Returns the schedule number of the row based on the form type and the tax tags """
        schedule_number = ''
        if form_type_code == '1601EQ':
            if '1601/1604A' in tags or '1601/1604B' in tags:
                schedule_number = '1'
            elif '1601/1604EX' in tags:
                schedule_number = '2'
        elif form_type_code == '1604E':
            if '1601/1604A' in tags or '1601/1604B' in tags:
                schedule_number = '3'
            elif '1601/1604EX' in tags:
                schedule_number = '4'
        return schedule_number

    def _sawt_qap_get_header_values(self, options):
        """ Each child reports have different fields they want in the header, so we will let them handle it. """
        return []

    def _sawt_qap_get_line_values(self, line, schedule, sequence, options):
        return []

    def _sawt_qap_get_schedule_control(self, lines, schedule, options):
        return []

    def _add_header_line(self, file_rows, categories_summed_amount, options):
        """ The header line in the SAWT & QAP reports is quite simple, but will differ based on the exact report & periodicity """
        header_row = self._sawt_qap_get_header_values(options)
        file_rows.append(','.join(header_row))

    def _add_details(self, file_rows, line_details, options):
        """ The SAWT & QAP reports have their details grouped by schedule (based on the tax), with a control line at the end of each group. """
        grouped_lines = defaultdict(list)
        form_type_code = options["form_type_code"]

        for line in line_details.values():
            schedule_number = self._get_schedule_number(form_type_code, line['tag_name'])
            grouped_lines[schedule_number].append(line)

        for schedule, lines in sorted(grouped_lines.items()):
            for i, line in enumerate(lines):
                line_values = self._sawt_qap_get_line_values(line, schedule, i, options)
                file_rows.append(','.join(line_values))
            control_values = self._sawt_qap_get_schedule_control(lines, schedule, options)
            file_rows.append(','.join(control_values))


class L10n_PhSawtReportHandler(models.AbstractModel):
    _name = 'l10n_ph.sawt.report.handler'
    _inherit = ['l10n_ph.sawt_qap.report.handler']
    _description = 'Sales Withholding Taxes Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.update({
            'journal_type': 'sale',
            # This mapping will be used to build the amount for each expression_label based on the grid names.
            'report_grids_map': {
                'tax_base_amount': ['1701/1702A'],
                'withholding_tax_amount': ['1701/1702B'],
            }
        })

    # ================
    # .DAT file export
    # ================

    def _get_available_form_to_export(self):
        return '1701Q,1701,1702Q,1702'

    def _sawt_qap_get_header_values(self, options):
        """ Returns a list containing the information we want to see in the header. """
        alpha_type = options["alpha_type"]
        form_type_code = options["form_type_code"]
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        return [
            self._format_value(f'H{alpha_type}', 6),
            self._format_value(f'H{form_type_code}', 7),
            self._format_value(company_vat, 9),
            self._format_value(company_branch, 4),
            self._format_value(company.partner_id.name, 50, quote=True),
            self._format_value(company.partner_id.last_name, 30, quote=True),
            self._format_value(company.partner_id.first_name, 30, quote=True),
            self._format_value(company.partner_id.middle_name, 30, quote=True),
            self._format_value(date_to.strftime('%m/%Y'), 7),
            self._format_value(company.partner_id.l10n_ph_rdo or '', 3),
        ]

    def _sawt_qap_get_line_values(self, line, schedule, sequence, options):
        alpha_type = options['alpha_type']
        form_type_code = options["form_type_code"]
        date_to = self._get_report_date_to(options)
        payee = self.env['res.partner'].browse(line.get('payee_id'))
        payee_vat, payee_branch = self._get_partner_vat_branch(payee.commercial_partner_id)

        return [
            self._format_value(f'D{alpha_type}', 6),
            self._format_value(f'D{form_type_code}', 7),
            str(sequence),  # Format value adds decimals, but here we just want a basic int
            self._format_value(payee_vat, 9),
            self._format_value(payee_branch, 4),
            self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
            self._format_value(line.get('payee_last_name', ''), 30, quote=True),
            self._format_value(line.get('payee_first_name', ''), 30, quote=True),
            self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
            self._format_value(date_to.strftime('%m/%Y'), 7),
            self._format_value(html2plaintext(line.get('income_nature', '')), 50, quote=True),
            self._format_value(line.get('atc_code', ''), 5),
            self._format_value(line.get('tax_rate', 0.0), 14),
            self._format_value(line.get('base_amount', 0.0), 14),
            self._format_value(line.get('withholding_tax_amount', 0.0), 14),
        ]

    def _sawt_qap_get_schedule_control(self, lines, schedule, options):
        alpha_type = options['alpha_type']
        form_type_code = options["form_type_code"]
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        # Sum the amounts in the lines
        total_withheld = 0.0
        total_base = 0.0
        for line in lines:
            total_base += line.get("base_amount", 0.0)
            total_withheld += line.get("withholding_tax_amount", 0.0)

        return [
            self._format_value(f'C{alpha_type}', 6),
            self._format_value(f'C{form_type_code}', 7),
            self._format_value(company_vat, 9),
            self._format_value(company_branch, 4),
            self._format_value(date_to.strftime('%m/%Y'), 7),
            self._format_value(total_base, 14),
            self._format_value(total_withheld, 14),
        ]


class L10n_PhQapReportHandler(models.AbstractModel):
    _name = 'l10n_ph.qap.report.handler'
    _inherit = ['l10n_ph.sawt_qap.report.handler']
    _description = 'Purchase Withholding Taxes Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.update({
            'journal_type': 'purchase',
            # This mapping will be used to build the amount for each expression_label based on the grid names.
            'report_grids_map': {
                'tax_base_amount': ['1601/1604A', '1601/1604EX'],
                'withholding_tax_amount': ['1601/1604B'],
            }
        })

    # ================
    # .DAT file export
    # ================

    def _get_available_form_to_export(self):
        return '1601EQ,1604E'

    def _sawt_qap_get_header_values(self, options):
        """ Returns a list containing the information we want to see in the header. """
        alpha_type = options["alpha_type"]
        form_type_code = options["form_type_code"]
        periodicity = options['periodicity']
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        if periodicity == 'quarterly':
            return [
                self._format_value(f'H{alpha_type}', 6),
                self._format_value(f'H{form_type_code}', 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(company.partner_id.name, 50, quote=True),
                self._format_value(date_to.strftime('%m/%Y'), 7),
                self._format_value(company.partner_id.l10n_ph_rdo or '', 3),
            ]
        else:
            return [
                self._format_value(f'H{form_type_code}', 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%d/%Y'), 10),
            ]

    def _sawt_qap_get_line_values(self, line, schedule, sequence, options):
        form_type_code = options["form_type_code"]
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)
        payee = self.env['res.partner'].browse(line.get('payee_id'))
        payee_vat, payee_branch = self._get_partner_vat_branch(payee.commercial_partner_id)
        date_to = self._get_report_date_to(options)

        if schedule == '1':
            return [
                self._format_value(f'D{schedule}', 2),
                self._format_value(form_type_code, 7),
                str(sequence),  # Format value adds decimals, but here we just want a basic int
                self._format_value(payee_vat, 9),
                self._format_value(payee_branch, 4),
                self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
                self._format_value(line.get('payee_last_name', ''), 30, quote=True),
                self._format_value(line.get('payee_first_name', ''), 30, quote=True),
                self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
                self._format_value(date_to.strftime('%m/%Y'), 7),
                self._format_value(line.get('atc_code', ''), 5),
                self._format_value(line.get('tax_rate', 0.0), 14),
                self._format_value(line.get('base_amount', 0.0), 14),
                self._format_value(line.get('withholding_tax_amount', 0.0), 14),
            ]
        elif schedule == '2':
            return [
                self._format_value(f'D{schedule}', 2),
                self._format_value(form_type_code, 7),
                str(sequence),  # Format value adds decimals, but here we just want a basic int
                self._format_value(payee_vat, 9),
                self._format_value(payee_branch, 4),
                self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
                self._format_value(line.get('payee_last_name', ''), 30, quote=True),
                self._format_value(line.get('payee_first_name', ''), 30, quote=True),
                self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
                self._format_value(date_to.strftime('%m/%Y'), 7),
                self._format_value(line.get('atc_code', ''), 5),
                self._format_value(line.get('base_amount', 0.0), 14),
            ]
        elif schedule == '3':
            return [
                self._format_value(f'D{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%d/%Y'), 10),
                str(sequence),  # Format value adds decimals, but here we just want a basic int
                self._format_value(payee_vat, 9),
                self._format_value(payee_branch, 4),
                self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
                self._format_value(line.get('payee_last_name', ''), 30, quote=True),
                self._format_value(line.get('payee_first_name', ''), 30, quote=True),
                self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
                self._format_value(line.get('atc_code', ''), 5),
                self._format_value(line.get('base_amount', 0.0), 14),
                self._format_value(line.get('tax_rate', 0.0), 14),
                self._format_value(line.get('withholding_tax_amount', 0.0), 14),
            ]
        else:
            return [
                self._format_value(f'D{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%d/%Y'), 10),
                str(sequence),  # Format value adds decimals, but here we just want a basic int
                self._format_value(payee_vat, 9),
                self._format_value(payee_branch, 4),
                self._format_value(line.get('payee_registered_name', ''), 50, quote=True),
                self._format_value(line.get('payee_last_name', ''), 30, quote=True),
                self._format_value(line.get('payee_first_name', ''), 30, quote=True),
                self._format_value(line.get('payee_middle_name', ''), 30, quote=True),
                self._format_value(line.get('atc_code', ''), 5),
                self._format_value(line.get('base_amount', 0.0), 14),
            ]

    def _sawt_qap_get_schedule_control(self, lines, schedule, options):
        form_type_code = options["form_type_code"]
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)
        date_to = self._get_report_date_to(options)

        # Sum the amounts in the lines
        total_withheld = 0.0
        total_base = 0.0
        for line in lines:
            total_base += line.get("base_amount", 0.0)
            total_withheld += line.get("withholding_tax_amount", 0.0)

        if schedule == '1':
            return [
                self._format_value(f'C{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%Y'), 7),
                self._format_value(total_base, 14),
                self._format_value(total_withheld, 14),
            ]
        elif schedule == '2':
            return [
                self._format_value(f'C{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%Y'), 7),
                self._format_value(total_base, 14),
            ]
        elif schedule == '3':
            return [
                self._format_value(f'C{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%d/%Y'), 10),
                self._format_value(total_withheld, 14),
            ]
        else:
            return [
                self._format_value(f'C{schedule}', 2),
                self._format_value(form_type_code, 7),
                self._format_value(company_vat, 9),
                self._format_value(company_branch, 4),
                self._format_value(date_to.strftime('%m/%d/%Y'), 10),
                self._format_value(total_base, 14),
            ]
