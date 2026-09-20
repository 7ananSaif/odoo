# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.tools import SQL, date_utils
from odoo.tools.misc import format_date


class L10n_PhSlspReportHandler(models.AbstractModel):
    _name = 'l10n_ph.slsp.report.handler'
    _inherit = ['l10n_ph.generic.report.handler']
    _description = 'Summary Lists of Sales and Purchases Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options.setdefault('buttons', []).append(
            {
                'name': _('Export SLSP'),
                'sequence': 5,
                'action': 'print_report_to_dat',
                'file_export_type': _('DAT'),
            }
        )
        # Initialise the custom options for this report.
        options['include_imports'] = previous_options.get('include_imports', False)

        options['custom_display_config']['components'] = {'AccountReportFilters': 'L10nPHSlspReportFilters'}

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
                  SELECT (date_trunc('month', account_move_line.date::DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE AS taxable_month,
                         %(column_group_key)s                                                                              AS column_group_key
                    FROM %(table_references)s
                   WHERE %(search_condition)s
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
            queries.append(SQL(
                """
                  SELECT %(column_group_key)s                                                                   AS column_group_key,
                         p.vat                                                                                  AS partner_vat,
                         COALESCE(
                             NULLIF(TRIM(CONCAT_WS(' ', p.last_name, p.first_name, p.middle_name)), ''),
                             p.name
                         )                                                                                      AS register_name,
                         p.id                                                                                   AS partner_id,
                         COALESCE(
                             NULLIF(TRIM(CONCAT_WS(' ', p.first_name, p.middle_name, p.last_name)), ''),
                             p.name
                         )                                                                                      AS partner_name,
                         p.last_name                                                                            AS last_name,
                         %(account_tag_name)s                                                                   AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                      AS balance
                    FROM %(table_references)s
                    JOIN res_partner p ON p.id = account_move_line__move_id.commercial_partner_id
                    %(currency_table_join)s
                   WHERE %(search_condition)s
                GROUP BY p.id, %(account_tag_name)s
                %(tail_query)s
                """,
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                column_group_key=column_group_key,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                currency_table_join=report._currency_table_aml_join(column_group_options),
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
        partners = self.env['res.partner'].browse([values['partner_id'] for values in data_dict])
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
                    'is_company': values['last_name'],
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
            'is_company': line_values['is_company'],  # This is only used when building the export, as we expect a slightly different behavior for companies
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
        lines_values = self._query_moves(report, options, partner_id, month, offset)
        return self._get_report_expand_unfoldable_line_value(report, options, line_dict_id, progress, lines_values, report_line_method=self._get_report_line_move)

    def _query_moves(self, report, options, partner_id, month, offset):
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
                  SELECT %(column_group_key)s                                                                   AS column_group_key,
                         account_move_line__move_id.id                                                          AS move_id,
                         account_move_line__move_id.name                                                        AS move_name,
                         %(account_tag_name)s                                                                   AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                      AS balance
                    FROM %(table_references)s
                    %(currency_table_join)s
                   WHERE %(search_condition)s
                GROUP BY account_move_line__move_id.id, %(account_tag_name)s
                %(tail_query)s
                """,
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                column_group_key=column_group_key,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                currency_table_join=report._currency_table_aml_join(column_group_options),
                table_references=query.from_clause,
                search_condition=query.where_clause,
                tail_query=tail_query,
            ))

        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        return self._process_move_lines(results, options)

    def _process_move_lines(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            # Initialise the move values
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
            'level': 2,
            'caret_options': 'account.move',
        }

    # ================
    # .DAT file export
    # ================

    def _get_dat_line_grouping_keys(self):
        return ['payee_id']

    def _slsp_get_header_values(self, categories_summed_amount, options):
        """ Each child reports have different fields they want in the header, so we will let them handle it. """
        return []

    def _slsp_get_line_values(self, line, options):
        """ Each child reports have different fields they want in the lines, so we will let them handle it. """
        return []

    def _add_header_line(self, file_rows, categories_summed_amount, options):
        header_row = self._slsp_get_header_values(categories_summed_amount, options)
        file_rows.append(','.join(header_row))

    def _add_details(self, file_rows, line_details, options):
        for line in line_details.values():
            line_values = self._slsp_get_line_values(line, options)
            file_rows.append(','.join(line_values))

    def _get_partner_address_lines(self, partner):
        """
        Prepare two strings representing the partner's address formated as required in the DAT file.
        :param partner: The partner for which we want to get the address lines.
        :return: The two strings representing the partner's address lines.
        """
        if partner.street2:
            address_1 = f'{partner.street2} {partner.street}'
        else:
            address_1 = partner.street or ''
        address_2 = f'{partner.city} {partner.state_id.name}'
        return address_1, address_2
