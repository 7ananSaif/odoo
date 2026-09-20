import json

from collections import defaultdict
from itertools import groupby

from odoo import models, fields, _
from odoo.tools import SQL


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _name = 'account.general.ledger.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'General Ledger Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Remove multi-currency columns if needed
        if self.env.user.has_group('base.group_multi_currency'):
            options['multi_currency'] = True
        else:
            options['columns'] = [
                column for column in options['columns']
                if column['expression_label'] != 'amount_currency'
            ]

        # Automatically unfold the report when printing it, unless some specific lines have been unfolded
        options['unfold_all'] = (options['export_mode'] == 'print' and not options.get('unfolded_lines')) or options['unfold_all']

        options['custom_display_config'] = {
            'templates': {
                'AccountReportLineName': 'account_reports.GeneralLedgerLineName',
            },
        }

    def _caret_options_initializer(self):
        default_caret = self.env['account.report']._caret_options_initializer_default()

        return {
            **default_caret,
            'id_with_accumulated_balance_caret': [
                {'name': _("View Journal Entry"), 'action': 'caret_option_open_record_form_custom_id_groupby', 'action_param': 'move_id'},
            ],
            'undistributed_profits_losses': [
                {'name': _("Journal Items"), 'action': 'open_unallocated_items_journal_items'},
            ],
        }

    def open_unallocated_items_journal_items(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        return report.open_unallocated_items_journal_items(options, params)

    def caret_option_open_record_form_custom_id_groupby(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        _model, aml_key = report._get_model_info_from_id(params['line_id'])
        record_id = json.loads(aml_key)[1]

        record = self.env['account.move.line'].browse(record_id)
        target_record = record[params['action_param']] if 'action_param' in params else record

        view_id = report._resolve_caret_option_view(target_record)

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')],  # view_id will be False in case the default view is needed
            'res_model': target_record._name,
            'res_id': target_record.id,
            'context': self.env.context,
        }

        if view_id is not None:
            action['view_id'] = view_id

        return action

    def _get_custom_groupby_map(self):
        def custom_label_builder(grouping_keys):
            """
            Batch label builder used to rename balance lines.
            """
            keys_names_in_sequence = {}

            ids_to_browse = []
            aml_keys = []
            for grouping_key in grouping_keys:
                if 'balance_line' in grouping_key:
                    keys_names_in_sequence[grouping_key] = _("Initial Balance")
                else:
                    combined_key = json.loads(grouping_key)
                    ids_to_browse.append(combined_key[1])
                    aml_keys.append(grouping_key)

            records_unsorted = self.env['account.move.line'].browse(ids_to_browse)
            for record, aml_key in zip(records_unsorted, aml_keys):
                keys_names_in_sequence[aml_key] = record.display_name

            return keys_names_in_sequence

        def domain_builder(grouping_key):
            if 'balance_line' in grouping_key:
                return []
            grouping_key_array = json.loads(grouping_key)
            return [('id', '=', grouping_key_array[1]), ('date', '=', grouping_key_array[0])]

        return {
            'id_with_accumulated_balance': {
                'model': None,
                'domain_builder': domain_builder,
                'caret_builder': lambda grouping_key: None if 'balance_line' in grouping_key else 'id_with_accumulated_balance_caret',
                'label_builder': custom_label_builder,
            },
        }

    def _report_custom_engine_general_ledger(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        def get_grouping_key(row, groupby):
            if groupby == 'id_with_accumulated_balance':
                if not row['id']:
                    return f"balance_line_{row['account_id']}"
                else:
                    return json.dumps([fields.Date.to_string(row['date']), row['id']])
            return row[groupby] if groupby else None

        report = self.env['account.report'].browse(options['report_id'])
        options_date_from = fields.Date.from_string(options['date']['date_from'])
        current_fiscalyear_date_from = self.env.company.compute_fiscalyear_dates(options_date_from)['date_from']

        # We want to exclude move lines from expense and income accounts before the fiscal year for every groupby under account_id
        additional_domain = [
            '|',
            ('account_id.include_initial_balance', '=', True),
            ('date', '>=', current_fiscalyear_date_from),
        ]

        report_query = report._get_report_query(options, 'from_beginning', additional_domain)

        if options.get('export_mode') == 'print' and options.get('filter_search_bar') and current_groupby not in ('id_with_accumulated_balance', 'id'):
            search_bar_sql = SQL(
                """
                AND result_account.id = ANY(%(search_bar_account_query)s)
                """,
                search_bar_account_query=self.env['account.account']._search([
                    ('display_name', 'ilike', options.get('filter_search_bar')),
                    *self.env['account.account']._check_company_domain(self.env['account.report'].get_report_company_ids(options)),
                ]).select(SQL.identifier('id'))
            )
        else:
            search_bar_sql = SQL()

        additional_select = SQL("")
        groupby = []
        if current_groupby == 'id_with_accumulated_balance':
            account_code_select = self.env['account.account']._field_to_sql('result_account', 'code', report_query)
            account_name_select = self.env['account.account']._field_to_sql('result_account', 'name')
            additional_select = SQL("""
                CASE
                    WHEN account_move_line.date >= %(date)s THEN account_move_line.id
                    ELSE NULL
                END AS id,
                CASE
                    WHEN account_move_line.date >= %(date)s THEN account_move_line.date
                    ELSE NULL
                END AS date,
                MIN(move.name) AS move_name,

                SUM(account_move_line.amount_currency) AS amount_currency,
                MIN(partner.name) AS partner_name,
                MIN(account_move_line.currency_id) AS currency_id,
                MIN(result_account.id) AS account_id,

                MIN(account_move_line.name) AS line_name,
                MIN(%(account_name_select)s) AS account_name,
                MIN(%(account_code_select)s) AS account_code,
                """,
                date=fields.Date.from_string(options['date']['date_from']),
                account_name_select=account_name_select,
                account_code_select=account_code_select,
            )
            groupby = [SQL("1"), SQL("2"), SQL("account_id")]
        elif current_groupby == 'account_id':
            additional_select = SQL("""
                result_account.id AS account_id,
                result_account.account_type AS account_type,
                SUM(account_move_line.amount_currency) AS amount_currency,
                result_account.currency_id AS currency_id,
            """)
            groupby = [SQL("result_account.id"), SQL("result_account.currency_id")]
        elif current_groupby:
            additional_select = SQL("%s,", self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query))
            groupby = [SQL("%s", self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query))]

        query = SQL(
            """
            SELECT
                %(additional_select)s
                COALESCE(SUM(%(select_debit)s), 0.0) AS debit,
                COALESCE(SUM(%(select_credit)s), 0.0) AS credit,
                COALESCE(SUM(%(select_balance)s), 0.0) AS balance
            FROM %(from_clause)s

            LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
            JOIN account_account account ON account.id = account_move_line.account_id
            JOIN account_account result_account ON result_account.id = account_move_line.account_id

            JOIN account_move move ON move.id = account_move_line.move_id
            %(currency_table_join)s

            WHERE %(where_clause)s
            %(search_bar_sql)s

            %(additional_groupby)s
            %(orderby_clause)s

            %(offset_clause)s
            LIMIT %(limit)s
            """,
            additional_select=additional_select,
            select_balance=report._currency_table_apply_rate(SQL("account_move_line.balance")),
            select_debit=report._currency_table_apply_rate(SQL("account_move_line.debit")),
            select_credit=report._currency_table_apply_rate(SQL("account_move_line.credit")),
            from_clause=report_query.from_clause,
            currency_table_join=report._currency_table_aml_join(options),
            where_clause=report_query.where_clause,
            search_bar_sql=search_bar_sql,
            additional_groupby=SQL("GROUP BY %s", SQL(",").join(groupby)) if groupby else SQL(),
            orderby_clause=SQL("ORDER BY 2 NULLS FIRST, move_name, 1 NULLS FIRST") if current_groupby == 'id_with_accumulated_balance' else SQL(),
            offset_clause=SQL("OFFSET %s", offset) if offset else SQL(),
            limit=limit
        )

        rows_by_key = defaultdict(lambda: {
            'date': None,
            'partner_name': None,
            'amount_currency': None,
            'currency_id': self.env.company.currency_id.id,
            'debit': 0,
            'credit': 0,
            'balance': 0,
            'has_sublines': True,
        })

        for row in self.env.execute_query_dict(query):
            aml_key = get_grouping_key(row, current_groupby)

            if aml_key not in rows_by_key:
                rows_by_key[aml_key].update({
                    'debit': row['debit'],
                    'credit': row['credit'],
                    'balance': row['balance'],
                })

                if current_groupby == 'id_with_accumulated_balance':
                    rows_by_key[aml_key]['has_sublines'] = False
                    rows_by_key[aml_key]['account_id'] = row['account_id']  # Needed for batching

                    if 'balance_line' not in aml_key:
                        rows_by_key[aml_key]['date'] = row['date']
                        rows_by_key[aml_key]['partner_name'] = row['partner_name']
                        rows_by_key[aml_key]['line_name'] = row['line_name']
                        rows_by_key[aml_key]['account_code'] = row['account_code']
                        rows_by_key[aml_key]['account_name'] = row['account_name']
                        rows_by_key[aml_key]['move_name'] = row['move_name']
                    if row['currency_id'] != self.env.company.currency_id.id:
                        rows_by_key[aml_key]['amount_currency'] = row['amount_currency']
                        rows_by_key[aml_key]['currency_id'] = row['currency_id']
                elif current_groupby == 'account_id':
                    rows_by_key[aml_key]['has_sublines'] = True
                    if row.get('currency_id'):
                        rows_by_key[aml_key]['amount_currency'] = row['amount_currency']
                        rows_by_key[aml_key]['currency_id'] = row['currency_id']
            else:
                rows_by_key[aml_key]['debit'] += row['debit']
                rows_by_key[aml_key]['credit'] += row['credit']
                rows_by_key[aml_key]['balance'] += row['balance']
                if row.get('currency_id'):
                    rows_by_key[aml_key]['currency_id'] += row['currency_id']

        if not current_groupby:
            return rows_by_key[None]  # None is the key for total line as there is no groupby

        return [(key, entry) for key, entry in rows_by_key.items()]

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        """
        Shadows the function from account_report.

        This allows us to use progress efficiently to compute the accumulated balance with partial expand capabilities
        """
        report = self.env['account.report'].browse(options['report_id'])
        result = report._report_expand_unfoldable_line_with_groupby(line_dict_id, groupby, options, progress, offset, unfold_all_batch_data)
        if groupby != 'id_with_accumulated_balance':
            return result

        colname_to_idx = defaultdict(dict)
        for idx, col in enumerate(options.get('columns', [])):
            colname_to_idx[col['column_group_key']][col['expression_label']] = idx

        if options['export_mode'] is None:
            limit_to_load = report.load_more_limit or None
        else:
            limit_to_load = None
            offset = 0

        processed_lines = result['lines']

        has_balance_line = False
        col_group_keys = options['column_groups']
        accumulated_balance_by_colgroup = progress.get('accumulated_balance_by_colgroup', {
            col_group_key: 0.0
            for col_group_key in col_group_keys
        })
        for col_group_key in col_group_keys:
            for line in processed_lines:
                line_balance = line['columns'][colname_to_idx[col_group_key]['balance']]['no_format']
                accumulated_balance_by_colgroup[col_group_key] += line_balance
                if line['name'] == 'balance_line':
                    has_balance_line = True
                    line['name'] = _("Initial Balance")
                else:
                    line['columns'][colname_to_idx[col_group_key]['balance']] = report._build_column_dict(accumulated_balance_by_colgroup[col_group_key], line['columns'][colname_to_idx[col_group_key]['balance']], options)

        return {
            **result,
            'lines': processed_lines,
            'offset_increment': limit_to_load - 1 if has_balance_line and limit_to_load else len(processed_lines),
            'progress': {
                **progress,
                'accumulated_balance_by_colgroup': accumulated_balance_by_colgroup,
            },
        }

    def _get_fiscalyear_start_date(self, options):
        options_date_from = fields.Date.to_date(options['date']['date_from'])
        return self.env.company.compute_fiscalyear_dates(options_date_from)['date_from']

    def _adjust_total_with_unaffected_earnings(self, total_line_columns, unaffected_earning_values):
        for col in total_line_columns:
            if col and col['expression_label'] in unaffected_earning_values:
                col['no_format'] += unaffected_earning_values[col['expression_label']]
                col['is_zero'] = not bool(col['no_format'])
        return total_line_columns

    def _custom_line_postprocessor(self, report, options, lines):
        """
        This post processor move the total line below the report as it should always be under in the general ledger
        """
        general_ledger_custom_engine_line = self.env.ref('account_reports.general_ledger_custom_engine_line')
        processed_lines = []
        main_line_dict = None
        account_move_lines = []
        unaffected_earning_values = defaultdict(float)

        # Get the unaffected earning lines if the whole report has been generated
        # (e.g., not when loading more lines in a group)
        if report._parse_line_id(lines[0]['id'])[-1] == ('', 'account.report.line', report.line_ids[0].id):
            unaffected_earning_lines = report._get_unallocated_earnings_lines(options, 'from_beginning')
        else:
            unaffected_earning_lines = []

        for line in lines + unaffected_earning_lines:
            markup, model, res_id = report._parse_line_id(line['id'])[-1]
            if model == 'account.report.line' and res_id == general_ledger_custom_engine_line.id:
                main_line_dict = line
            elif markup == 'undistributed_profits_losses':
                for column in line['columns']:
                    # Swap no_format from 0.0 to None for unaffected lines, to match the other lines
                    if column['expression_label'] == 'amount_currency' and column['is_zero']:
                        column['no_format'] = None
                    elif column['figure_type'] == 'monetary':
                        unaffected_earning_values[column['expression_label']] += column['no_format']
            else:
                processed_lines.append(line)

            if (
                model is None and markup == {'groupby': 'id_with_accumulated_balance'}
                and not res_id.startswith('balance_line_') and options.get('export_mode') != 'file'
            ):
                line['chatter'] = {'id': json.loads(res_id)[1]}
                account_move_lines.append(line)

        if account_move_lines:
            line_ids = (l['chatter']['id'] for l in account_move_lines)
            account_moves = {
                line['id']: line['move_id'][0]
                for line in self.env['account.move.line'].browse(line_ids).read(['id', 'move_id'])
            }
            for line in account_move_lines:
                line['chatter']['id'] = account_moves[line['chatter']['id']]
                line['chatter']['model'] = 'account.move'

        if self.env.company.totals_below_sections and not options.get('ignore_totals_below_sections'):
            if unaffected_earning_lines:
                total_line = processed_lines.pop(-1)
                total_line['columns'] = self._adjust_total_with_unaffected_earnings(total_line['columns'], unaffected_earning_values)
                processed_lines.extend(unaffected_earning_lines)
                processed_lines.append(total_line)
            return processed_lines

        processed_lines.extend(unaffected_earning_lines)
        if main_line_dict:
            processed_lines.append({
                'id': report._get_generic_line_id(None, None, 'total'),
                'name': _("Total General Ledger"),
                'columns': self._adjust_total_with_unaffected_earnings(main_line_dict['columns'], unaffected_earning_values),
                'level': 1
            })

        return processed_lines

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        """ Generate the custom engine's results for each full-sub-groupby-key that
            would be created when doing an unfold-all on the report.
        """

        results = {}  # In the form {full_sub_groupby_key: all_column_group_expression_totals for this groupby computation}

        for line_to_expand in lines_to_expand_by_function.get('_report_expand_unfoldable_line_with_groupby', []):
            report_line_id = report._get_res_id_from_line_id(line_to_expand['id'], 'account.report.line')
            report_line = self.env['account.report.line'].browse(report_line_id)

            expressions = report_line.expression_ids.filtered(
                lambda x: x.engine == 'custom' and x.formula == '_report_custom_engine_general_ledger'
            )
            if not expressions:
                continue

            for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
                for date_scope, expressions_by_date_scope in groupby(expressions, lambda e: e.date_scope):
                    expressions_by_date_scope = list(expressions_by_date_scope)
                    # Get the custom engine results for the given groupby level.
                    engine_account_lines = self._report_custom_engine_general_ledger(expressions_by_date_scope, column_group_options, date_scope, 'account_id', 'id_with_accumulated_balance')
                    account_expression_totals = results.setdefault(f"[{report_line_id}]=>account_id", {})\
                                                        .setdefault(column_group_key, {expression: {'value': [], 'sublines_info': set()} for expression in expressions_by_date_scope})
                    for account_id, engine_account_result_dict in engine_account_lines:
                        for expression in expressions_by_date_scope:
                            account_expression_totals[expression]['value'].append(
                                (account_id, engine_account_result_dict[expression.subformula])
                            )
                            if engine_account_result_dict['has_sublines']:
                                account_expression_totals[expression]['sublines_info'].add(account_id)

                    engine_aml_lines = self._report_custom_engine_general_ledger(expressions_by_date_scope, column_group_options, date_scope, 'id_with_accumulated_balance', None)
                    aml_data_by_account = {}
                    for grouping_key, engine_result_dict in engine_aml_lines:
                        engine_result_dict['grouping_key'] = grouping_key
                        aml_data_by_account.setdefault(engine_result_dict['account_id'], []).append(engine_result_dict)

                    for account_id, engine_result_list in aml_data_by_account.items():
                        account_aml_expression_totals = results.setdefault(f"[{report_line_id}]account_id:{account_id}=>id_with_accumulated_balance", {})\
                                                            .setdefault(column_group_key, {expression: {'value': [], 'sublines_info': set()} for expression in expressions_by_date_scope})
                        for engine_result_dict in engine_result_list:
                            for expression in expressions_by_date_scope:
                                account_aml_expression_totals[expression]['value'].append(
                                    (engine_result_dict['grouping_key'], engine_result_dict[expression.subformula])
                                )

        return results
