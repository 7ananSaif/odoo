from odoo import models
from odoo.tools import SQL


class CarbonReportHandler(models.AbstractModel):
    _name = 'esg.carbon.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Carbon Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options['float_rounding'] = 2

        selected_gas = {
            gas_option.get('code') for gas_option in previous_options.get('carbon_report_selected_gas', [])
            if gas_option.get('selected') and gas_option.get('code')
        }

        options['carbon_report_selected_gas'] = [
            {'name': gas.name, 'id': gas.id, 'selected': gas.code in selected_gas, 'code': gas.code}
            for gas in self.env['esg.gas'].sudo().search([])
        ]

        options['columns'] = [col_opt for col_opt in options['columns'] if col_opt['expression_label'] in {*selected_gas, 'co2e'}]

        options['custom_display_config'] = {
            'templates': {
                'AccountReportFilters': 'esg.CarbonReportFilters',
            }
        }

    def _report_custom_engine_carbon_report(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        report._check_groupby_fields((next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        query = report._get_report_query(options, date_scope)

        groupby_sql = ''
        # Handle custom groupby values supported by this report
        if current_groupby == 'carbon_report_source_hierarchy':
            groupby_sql = SQL('esg_emission_source.id')
        elif current_groupby == 'carbon_report_source_scope':
            groupby_sql = SQL('esg_emission_source.scope')
        elif current_groupby:
            groupby_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query)

        stored_aml_fields, emission_shadowing_fields_to_insert = self.env['account.move.line']._prepare_aml_shadowing_for_report({
            'date': SQL.identifier('esg_other_emission', 'date'),
            'esg_emission_factor_id': SQL.identifier('esg_other_emission', 'esg_emission_factor_id'),
            'quantity': SQL.identifier('esg_other_emission', 'quantity'),
            'company_id': SQL.identifier('esg_other_emission', 'company_id'),
            'esg_emission_multiplicator': SQL.identifier('esg_other_emission', 'esg_emission_multiplicator'),
            'parent_state': 'posted',
            'display_type': 'product',
        }, prefix_fields=True)

        filtered_gas_select = SQL(', ').join(
            SQL(
                """
                    COALESCE(
                        SUM(
                            CASE WHEN esg_emission_factor_line.gas_id = %(gas_id)s
                            THEN esg_emission_factor_line.quantity * account_move_line.esg_emission_multiplicator
                            ELSE 0
                            END
                        ) / 1000, -- /1000 to express it in tons instad of kg
                        0
                ) AS %(gas_label)s
                """,
                gas_id=gas_opt['id'],
                gas_label=SQL.identifier(gas_opt['code']),
            )
            for gas_opt in options['carbon_report_selected_gas']
        )

        report_sql = SQL(
            """
                SELECT
                    %(filtered_gas_select)s

                    COALESCE(
                        SUM(
                            CASE WHEN esg_emission_factor_line.id IS NULL THEN
                                -- For emission factors without any gas line
                                esg_emission_factor.esg_emissions_value * account_move_line.esg_emission_multiplicator
                            ELSE
                                esg_emission_factor_line.esg_emissions_value * account_move_line.esg_emission_multiplicator
                            END
                        ),
                        0
                    ) / 1000 AS co2e
                    -- /1000 to express it in tons instad of kg

                    %(select_groupby_sql)s
                FROM (
                    -- Local shadowing ; we extend the account_move_line table artificially

                    SELECT %(stored_aml_fields)s
                    FROM %(table_references)s
                    WHERE account_id IN (
                        SELECT id
                        FROM account_account
                        WHERE account_type IN %(valid_account_types)s
                    )

                    UNION ALL

                    SELECT %(emission_shadowing_fields_to_insert)s
                    FROM esg_other_emission
                    JOIN esg_emission_factor other_emission_factor
                        ON other_emission_factor.id = esg_other_emission.esg_emission_factor_id
                ) AS %(table_references)s
                JOIN esg_emission_factor
                    ON esg_emission_factor.id = account_move_line.esg_emission_factor_id
                JOIN esg_emission_source
                    ON esg_emission_source.id = esg_emission_factor.source_id
                LEFT JOIN esg_emission_factor_line
                    ON esg_emission_factor_line.esg_emission_factor_id = esg_emission_factor.id
                WHERE
                %(search_condition)s
                %(group_by_groupby_sql)s
                %(order_by_sql)s
                %(query_tail)s
            """,
            filtered_gas_select=SQL("%s, ", filtered_gas_select) if filtered_gas_select else SQL(),
            select_groupby_sql=SQL(', %s AS grouping_key', groupby_sql) if groupby_sql else SQL(),
            table_references=query.from_clause,
            stored_aml_fields=stored_aml_fields,
            valid_account_types=self.env['account.account'].ESG_VALID_ACCOUNT_TYPES,
            emission_shadowing_fields_to_insert=emission_shadowing_fields_to_insert,
            search_condition=query.where_clause,
            group_by_groupby_sql=SQL('GROUP BY %s', groupby_sql) if groupby_sql else SQL(),
            order_by_sql=SQL(' ORDER BY %s', groupby_sql) if groupby_sql else SQL(),
            query_tail=report._get_engine_query_tail(offset, limit),
        )

        self.env.cr.execute(report_sql)
        query_res_lines = self.env.cr.dictfetchall()

        gas_labels = [gas_opt['code'] for gas_opt in options['carbon_report_selected_gas']] + ['co2e']
        if not current_groupby:
            return {gas_label: query_res_lines[0][gas_label] for gas_label in gas_labels}
        elif current_groupby == 'carbon_report_source_hierarchy':
            source_parents = {
                source.id: source.parent_id.id or None
                for source in self.env['esg.emission.source'].sudo().search([])
            }
            highest_emission_source_in_hierarchy = self.env.context.get('highest_emission_source_in_hierarchy')
            totals_including_child_sources = {}  # in the form {source_id: {gas: value}}
            sources_with_sublines = set()

            for query_res in query_res_lines:
                # Find the highest parent that can be displayed ; it will receive the value of all its children
                source_id = query_res['grouping_key']
                while (source_parent := source_parents.get(source_id)) and source_parent != highest_emission_source_in_hierarchy:
                    source_id = source_parent

                if source_parent == highest_emission_source_in_hierarchy:
                    source_totals = totals_including_child_sources.setdefault(source_id, {})
                    for gas_label in gas_labels:
                        source_totals.setdefault(gas_label, 0)
                        source_totals[gas_label] += query_res[gas_label]
                    if source_id != query_res['grouping_key']:
                        sources_with_sublines.add(source_id)

            return [
                (source_id, {**source_totals, 'has_sublines': source_id in sources_with_sublines})
                for source_id, source_totals in totals_including_child_sources.items()
            ]
        else:
            return [
                (query_res['grouping_key'], {**{gas_label: query_res[gas_label] for gas_label in gas_labels}, 'has_sublines': True})
                for query_res in query_res_lines
            ]

    def _custom_groupby_line_completer(self, report, options, line_dict, current_groupby):
        if current_groupby == 'carbon_report_source_hierarchy':
            if line_dict.get('unfoldable'):
                esg_source_id = report._get_model_info_from_id(line_dict['id'])[1]
                esg_source = self.env['esg.emission.source'].browse(esg_source_id)

                if esg_source.child_ids:
                    line_dict.update({
                        'groupby': f"carbon_report_source_hierarchy,{line_dict['groupby']}",
                        'expand_function': '_report_expand_unfoldable_line_with_groupby_emission_source',
                    })
            elif line_dict.get('groupby'):
                # This will happen when has_sublines gives a falsy value in the custom engine.
                # In this case, if there is still a level of grouping, we stop the hierarchy cycling.
                # We then need to make the line unfoldable again, to allow proceeding to this next groupby level.
                line_dict['unfoldable'] = True

        if current_groupby in ('carbon_report_source_scope', 'carbon_report_source_hierarchy', 'esg_emission_factor_id'):
            for col_dict in filter(lambda x: x['expression_label'] == 'co2e', line_dict['columns']):
                col_dict['auditable'] = True

    def _get_custom_groupby_map(self):
        def carbon_report_source_hierarchy_label_builder(grouping_keys):
            keys_and_names_in_sequence = {}
            for emission_source in self.env['esg.emission.source'].browse(grouping_keys):
                keys_and_names_in_sequence[emission_source.id] = emission_source.name
            return keys_and_names_in_sequence

        def carbon_report_source_scope_label_builder(grouping_keys):
            keys_and_names_in_sequence = {}
            labels_dict = dict(self.env['esg.emission.source']._fields['scope']._description_selection(self.env))
            for grouping_key in grouping_keys:
                keys_and_names_in_sequence[grouping_key] = labels_dict[grouping_key]
            return keys_and_names_in_sequence

        return {
            'carbon_report_source_hierarchy': {
                'model': 'esg.emission.source',
                'domain_builder': lambda source_id: [('esg_emission_factor_id.source_id', 'child_of', source_id)],
                'label_builder': carbon_report_source_hierarchy_label_builder,
            },
            'carbon_report_source_scope': {
                'model': None,
                'domain_builder': lambda scope: [('esg_emission_factor_id.source_id.scope', '=', scope)],
                'label_builder': carbon_report_source_scope_label_builder,
            },
        }

    def _report_expand_unfoldable_line_with_groupby_emission_source(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        # esg.emission_source model defines a recursive hierarchy of records. This custom groupby behaves differently
        # than the traditional groupby used by reports, in that it will not always correspond to a single level of lines.
        # To handle that, we use this custom expand function, which uses a specific context key to limit the next unfolding, and restores
        # the same groupby on the next level if needed.
        report = self.env['account.report'].browse(options['report_id'])

        unfolded_source_id = report._get_res_id_from_line_id(line_dict_id, 'esg.emission.source')
        if unfolded_source_id:
            report = report.with_context(highest_emission_source_in_hierarchy=unfolded_source_id)

        return report._report_expand_unfoldable_line_with_groupby(
            line_dict_id,
            groupby,
            options,
            progress,
            offset,
            unfold_all_batch_data=unfold_all_batch_data,
        )

    def action_audit_cell(self, options, params):
        report = self.env['account.report'].browse(options['report_id'])
        parsed_line_id = report._parse_line_id(params['calling_line_dict_id'])
        markup, _dummy, value = parsed_line_id[-1]
        if markup == 'total':
            markup, _dummy, value = parsed_line_id[-2]

        domain = [('date', '>=', options['date']['date_from']), ('date', '<=', options['date']['date_to'])]
        if markup.get('groupby') == 'carbon_report_source_scope':
            domain += [('scope', '=', value)]
        elif markup.get('groupby') == 'carbon_report_source_hierarchy':
            domain += [('source_id', 'child_of', value)]
        elif markup.get('groupby') == 'esg_emission_factor_id':
            domain += [('esg_emission_factor_id', '=', value)]

        # Other groupings aren't auditable

        return {
            'name': self.env._("Audit Emissions"),
            'type': 'ir.actions.act_window',
            'res_model': 'esg.carbon.emission.report',
            'view_mode': 'list',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
        }
