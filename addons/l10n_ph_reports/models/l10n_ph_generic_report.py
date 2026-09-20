# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.tools.sql import SQL


class L10n_PhGenericReportHandler(models.AbstractModel):
    _name = 'l10n_ph.generic.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Philippines Generic Report Custom Handler'

    def _get_options_domain(self, options):
        options_domain = Domain.TRUE
        if 'journal_type' in options:
            if options['journal_type'] == 'sale':
                payment_type = 'inbound'
                opposite_payment_type = 'outbound'
                credit_note_type = 'out_refund'
                move_types = self.env['account.move'].get_sale_types(include_receipts=True)
            else:
                payment_type = 'outbound'
                opposite_payment_type = 'inbound'
                credit_note_type = 'in_refund'
                move_types = self.env['account.move'].get_purchase_types(include_receipts=True)
            options_domain = (
                Domain("move_id.move_type", "in", move_types)
                | Domain(
                    "move_id.origin_payment_id",
                    "any",
                    Domain("invoice_ids.move_type", "in", move_types)
                    & Domain("payment_type", "=", payment_type),
                )
                | Domain(
                    "move_id.origin_payment_id",
                    "any",
                    Domain("invoice_ids.move_type", "=", credit_note_type)
                    & Domain("payment_type", "=", opposite_payment_type),
                )
            )
        if 'include_no_tin' in options and not options['include_no_tin']:
            options_domain &= Domain("move_id.partner_id.vat", "!=", False)
        return options_domain

    def _get_report_query(self, report, column_group_options, with_base_lines=True, with_tax_lines=True, extra_domain=None):
        """
        Build on top of the query from account_report._get_report_query in order to add generic conditions and joins.
        This will add WHERE for the extra options specific to our PH reports, as well as joins providing correct access
        to account_tax and account_tag for each line.

        Using this will ensure that the query properly support withholding taxes on both invoices and payment, as well as
        other taxes as needed, and will always correctly filter based on the options.
        """
        options_domain = self._get_options_domain(column_group_options)
        if extra_domain:
            options_domain = Domain.AND([options_domain, extra_domain])
        query = report._get_report_query(column_group_options, date_scope="strict_range", domain=options_domain)

        query.add_join(
            kind='JOIN',
            alias='account_tag_rel',
            table='account_account_tag_account_move_line_rel',
            condition=SQL("account_tag_rel.account_move_line_id = account_move_line.id"),
        )
        query.add_join(
            kind='JOIN',
            alias='account_tag',
            table='account_account_tag',
            condition=SQL("account_tag.id = account_tag_rel.account_account_tag_id"),
        )
        table_join_conditions = []
        if with_base_lines:
            query.add_join(
                kind='LEFT JOIN',
                alias='tax_rel',
                table='account_move_line_account_tax_rel',
                condition=SQL("account_move_line.id = tax_rel.account_move_line_id"),
            )
            table_join_conditions.append(SQL("account_tax.id = tax_rel.account_tax_id"))
        if with_tax_lines:
            table_join_conditions.append(SQL("account_tax.id = account_move_line.tax_line_id"))
        query.add_join(
            kind='JOIN',
            alias='account_tax',
            table='account_tax',
            condition=SQL(" OR ").join(table_join_conditions),
        )
        # Otherwise you could have duplicated rows as the tax & tags are not "linked" in the joins.
        query.add_where("""EXISTS (
            SELECT 1
            FROM account_tax_repartition_line atrl
            JOIN account_account_tag_account_tax_repartition_line_rel aatatrlr ON atrl.id = aatatrlr.account_tax_repartition_line_id
            WHERE atrl.tax_id = account_tax.id AND aatatrlr.account_account_tag_id = account_tag.id
        )""")

        return query

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        # Initialise the custom options for this report.
        options['include_no_tin'] = previous_options.get('include_no_tin', True)
        options.setdefault('custom_display_config', {}).setdefault('components', {})['AccountReportFilters'] = 'L10nPHReportFilters'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        report_lines = self._build_month_lines(report, options)
        if grand_total_line := self._build_grand_total_line(report, options):
            report_lines.append(grand_total_line)

        # Inject sequences on the dynamic lines
        return [(0, line) for line in report_lines]

    def _build_month_lines(self, report, options):
        # TO OVERRIDE
        return []

    def _get_report_expand_unfoldable_line_value(self, report, options, line_dict_id, progress, lines_values, *, report_line_method):
        lines = []
        has_more = False
        treated_results_count = 0
        next_progress = progress

        for line_key, line_values in lines_values.items():
            if options['export_mode'] != 'print' and report.load_more_limit and treated_results_count == report.load_more_limit:
                # We loaded one more than the limit on purpose: this way we know we need a "load more" line
                has_more = True
                break

            new_line = report_line_method(report, options, line_key, line_values, parent_line_id=line_dict_id)
            lines.append(new_line)
            next_progress = {
                column['column_group_key']: line_col.get('no_format', 0)
                for column, line_col in zip(options['columns'], new_line['columns'])
                if column['expression_label'] == 'balance'
            }
            treated_results_count += 1

        return {
            'lines': lines,
            'offset_increment': treated_results_count,
            'has_more': has_more,
            'progress': next_progress,
        }

    def _get_line_columns(self, report, options, data):
        line_columns = []
        for column in options['columns']:
            col_value = data[column['column_group_key']].get(column['expression_label'])
            line_columns.append(report._build_column_dict(
                col_value=col_value or '',
                col_data=column,
                options=options,
            ))
        return line_columns

    def _eval_report_grids_map(self, options, data, *, column_values):
        """ Evaluate the report grids map for the given tax group and lines values. """
        # Sum the balances on the right expression label.
        # We use a map of tax grids to do that easily
        report_grids_map = options['report_grids_map']
        for expression_label, grids in report_grids_map.items():
            if expression_label not in column_values:
                column_values[expression_label] = 0
            if data['tag_name'] in grids:  # In this report, we always sum, so it's easy
                column_values[expression_label] += data['balance']

    def _filter_lines_with_values(self, options, lines_values, ignored_grids=[]):
        lines_with_values = {}
        report_grids_map = options['report_grids_map']
        for line, value in lines_values.items():
            for column_group_key in options['column_groups']:
                if any(value[column_group_key][grid] != 0 for grid in report_grids_map if grid not in ignored_grids):
                    lines_with_values[line] = value

        return lines_with_values

    # Grand total
    def _build_grand_total_line(self, report, options):
        """ The grand total line is the sum of all values in the given reporting period. """
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = self._get_report_query(report, column_group_options)
            queries.append(SQL(
                """
                  SELECT %(column_group_key)s                                                                               AS column_group_key,
                         %(account_tag_name)s                                                                               AS tag_name,
                         SUM(%(balance_select)s
                             * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                         )                                                                                                  AS balance
                    FROM %(table_references)s
                    %(currency_table_join)s
                   WHERE %(search_condition)s
                GROUP BY column_group_key, %(account_tag_name)s
                """,
                column_group_key=column_group_key,
                account_tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
                balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                currency_table_join=report._currency_table_aml_join(column_group_options),
                table_references=query.from_clause,
                search_condition=query.where_clause,
            ))
        results = self.env.execute_query_dict(SQL(" UNION ALL ").join(queries))
        return results and self._get_report_line_grand_total(report, options, self._process_grand_total_line(results, options))

    def _process_grand_total_line(self, data_dict, options):
        """ Taking in the values from the database, this will construct the column values by using the tax grid mapping
        set in the option of each report section.
        """
        lines_values = {}
        for values in data_dict:
            if values['column_group_key'] not in lines_values:
                lines_values[values['column_group_key']] = lines_values
            self._eval_report_grids_map(options, values, column_values=lines_values[values['column_group_key']])
        return lines_values

    def _get_report_line_grand_total(self, report, options, res):
        """ Format the given values to match the report line format. """
        line_columns = self._get_line_columns(report, options, res)
        line_id = report._get_generic_line_id('', '', markup='grand_total')
        return {
            'id': line_id,
            'name': _('Grand Total'),
            'unfoldable': False,
            'unfolded': False,
            'columns': line_columns,
            'level': 0,
        }

    # ================
    # .DAT file export
    # ================

    def print_report_to_dat(self, options):
        report = self.env['account.report'].browse(options.get('selected_section_id') or options['report_id'])
        custom_handler = self.env[report._get_custom_handler_model()]

        new_wizard = self.env['l10n_ph_reports.dat.file.export'].create([{
            'available_forms': custom_handler._get_available_form_to_export(),
        }])
        return {
            'name': 'DAT Export Options',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'res_model': 'l10n_ph_reports.dat.file.export',
            'type': 'ir.actions.act_window',
            'res_id': new_wizard.id,
            'target': 'new',
            'context': dict(self.env.context, l10n_ph_reports_generation_options=options),
        }

    def _get_available_form_to_export(self):
        """
        Returns a comma separated string of values that will populate the selection of possible
        forms for which we need the DAT file.
        """
        return ''

    @api.model
    def export_report_to_dat(self, options):
        """
        Called indirectly by the DAT export wizard, this will return the details of the file to be downloaded based
        on the current report section and as well as the form type chosen by the user.
        """
        report = self.env['account.report'].browse(options.get('selected_section_id') or options['report_id'])
        custom_handler = self.env[report._get_custom_handler_model()]

        # We start by gathering the data necessary for all exports (tax info as well as their base amounts)
        base_line_details = custom_handler._get_base_line_details(report, options)  # Includes the partners' info
        tax_line_details = custom_handler._get_tax_line_details(report, options)
        # We then group the lines together; adding the tax line details to the base line.
        # And also categorize the line amounts based on their tags, using the info we get from report_grids_map
        line_details = custom_handler._aggregate_and_group_lines(base_line_details, tax_line_details, options)
        filtered_line_details = {key: line for key, line in line_details.items() if line.get('base_amount', 0.0) != 0}

        # With the amounts now prepared, we finish by summing up all categories to get their total needed in some case.
        categories_summed_amount = custom_handler._sum_tax_categories(filtered_line_details, options)

        # We now have all the data we could need under our hands, so we can start building the file.
        # These are more specific to the report types so the file generation is going to be handled in the subclasses.
        file_rows = []

        # Every file has a header line.
        custom_handler._add_header_line(file_rows, categories_summed_amount, options)

        # Some files will have control lines along their data and others won't.
        # We leave that to the report itself, and just export the "details"
        custom_handler._add_details(file_rows, filtered_line_details, options)

        # At this stage we have all our lines, we only need to build the final file.
        file_data = '\n'.join(file_rows)
        return {
            'file_name': custom_handler._get_dat_file_name(options),
            'file_content': file_data,
            'file_type': 'dat',
        }

    # Preparation of data

    def _get_base_line_details(self, report, options):
        """ Gather the information about tax base line amounts, including the partner information. """
        query = self._get_report_query(report, options, with_tax_lines=False)

        # Gather the tax tags that concern this particular report.
        grid_map = options['report_grids_map']
        tags = {tag for category, tags in grid_map.items() for tag in tags}

        query = SQL(
            '''
            SELECT
                partner.id                                    AS payee_id,
                partner.vat                                   AS payee_tin,
                partner.branch_code                           AS payee_branch_code,
                partner.name                                  AS payee_registered_name,
                partner.last_name                             AS payee_last_name,
                partner.first_name                            AS payee_first_name,
                partner.middle_name                           AS payee_middle_name,
                account_tax.id                                AS tax_id,
                account_tax.l10n_ph_atc                       AS atc_code,
                %(tax_description)s                           AS income_nature,
                ABS(account_tax.amount)                       AS tax_rate,
                %(tag_name)s                                  AS tag_name,
                SUM(%(balance_select)s
                    * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                )                                             AS base_amount
            FROM %(table_references)s
            JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
                %(currency_table_join)s
            WHERE %(search_condition)s
            AND %(tag_name)s IN %(tags)s
            GROUP BY partner.id, account_tax.id, tag_name
            ORDER BY partner.name, account_tax.l10n_ph_atc, tag_name
            ''',
            tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
            balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
            tax_description=self.env['account.tax']._field_to_sql('account_tax', 'description', query),
            tags=tuple(tags),
            balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
            currency_table_join=report._currency_table_aml_join(options),
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )

        return self.env.execute_query_dict(query)

    def _get_tax_line_details(self, report, options):
        """ Gather the information about tax line amounts. """
        query = self._get_report_query(report, options, with_base_lines=False)

        # Gather the tax tags that concern this particular report.
        grid_map = options['report_grids_map']
        tags = {tag for category, tags in grid_map.items() for tag in tags}

        query = SQL(
            '''
            SELECT
                partner.id                                                           AS payee_id,
                partner.vat                                                          AS payee_tin,
                partner.branch_code                                                  AS payee_branch_code,
                partner.name                                                         AS payee_registered_name,
                partner.last_name                                                    AS payee_last_name,
                partner.first_name                                                   AS payee_first_name,
                partner.middle_name                                                  AS payee_middle_name,
                account_tax.id                                                       AS tax_id,
                %(tag_name)s                                                         AS tag_name,
                SUM(%(balance_select)s
                    * CASE WHEN %(balance_negate)s THEN -1 ELSE 1 END
                )                                                                    AS tax_amount
            FROM %(table_references)s
            JOIN res_partner partner ON partner.id = account_move_line__move_id.commercial_partner_id
                %(currency_table_join)s
            WHERE %(search_condition)s
            AND %(tag_name)s IN %(tags)s
            GROUP BY partner.id, account_tax.id, tag_name
            ORDER BY partner.name, account_tax.l10n_ph_atc, tag_name
            ''',
            tag_name=self.env['account.account.tag'].with_context(lang='en_US')._field_to_sql('account_tag', 'name', query),
            balance_negate=self.env['account.account.tag']._field_to_sql('account_tag', 'balance_negate', query),
            tags=tuple(tags),
            balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
            currency_table_join=report._currency_table_aml_join(options),
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )

        return self.env.execute_query_dict(query)

    def _get_dat_line_grouping_keys(self):
        return ['']

    def _aggregate_and_group_lines(self, base_line_details, tax_line_details, options):
        """
        Take the base lines and tax lines, and group them together based on the result of _get_dat_line_grouping_keys.

        The amounts will be spread in the resulting lines based on the categories and tags defined in report_grids_map.
        """
        lines = defaultdict(dict)
        grouping_keys = self._get_dat_line_grouping_keys()
        grid_map = options['report_grids_map']
        categories_per_tag = defaultdict(list)
        for category, tags in grid_map.items():
            for tag in tags:
                categories_per_tag[tag].append(category)

        for base_line in base_line_details:
            group = '-'.join(str(base_line[key]) for key in grouping_keys)
            tax_categories = categories_per_tag[base_line['tag_name']]

            if group not in lines:
                lines[group] = base_line

            # If the tag is part of multiple categories, we need to be sure that we affect all of them
            for tax_category in tax_categories:
                if tax_category in lines[group]:
                    lines[group][tax_category] += base_line['base_amount']
                else:
                    lines[group][tax_category] = base_line['base_amount']

        for tax_line in tax_line_details:
            group = '-'.join(str(tax_line[key]) for key in grouping_keys)
            tax_categories = categories_per_tag[tax_line['tag_name']]

            for tax_category in tax_categories:
                if tax_category in lines[group]:
                    lines[group][tax_category] += tax_line['tax_amount']
                else:
                    lines[group][tax_category] = tax_line['tax_amount']
        return lines

    def _sum_tax_categories(self, line_details, options):
        # Gather the categories that concern this particular report.
        grid_map = options['report_grids_map']
        categories_summed_amount = defaultdict(int)

        for line in line_details.values():
            for category in grid_map:
                if category in line:
                    categories_summed_amount[category] += line[category]

        return categories_summed_amount

    # Building of the file

    def _get_dat_file_name(self, options):
        company = self.env["res.company"].browse(options["companies"][0]["id"])
        form_type_code = options["form_type_code"]
        date_to = self._get_report_date_to(options)

        filename_date_format = options['filename_date_format']
        return_period = date_to.strftime(filename_date_format)
        company_vat, company_branch = self._get_partner_vat_branch(company.partner_id)

        return f"{company_vat}{company_branch}{return_period}{form_type_code}.dat"

    def _add_header_line(self, file_rows, categories_summed_amount, options):
        """
        To be implemented in the child classes.

        This should add the header line in the file_rows list.
        """
        raise NotImplementedError

    def _add_details(self, file_rows, line_details, options):
        """
        To be implemented in the child classes.

        This should add the detail lines in the file_rows list.
        """
        raise NotImplementedError

    # helpers

    @api.model
    def _get_partner_vat_branch(self, partner):
        """
        Small helper which returns the vat as well as the branch of the provided partner.
        In Odoo, the branch is part of the VAT number but the export file wants them separate.
        """
        vat = partner.vat and re.sub(r'\D', '', partner.vat)
        if not vat:
            return '', ''

        # For the vat, we want to only keep the numbers, no separators/... and only the first 9 digits are the VAT
        # For the branch code, we want it to always be four characters even if it is 5 in the VAT number.
        branch_code = (partner.branch_code or vat[9:])[-4:].rjust(4, '0')
        return vat[:9], branch_code

    @api.model
    def _format_value(self, value, max_width, quote=False):
        """
        General purpose formater to format a value to the expecting string representation in the dat file.
        The width given should most of the time come from the file specifications.
        """
        # 0 Should be formatted as number too
        if value is not None and value is not False and isinstance(value, (int, float)):
            value = f'{value:.2f}'
        value = str(value or "").strip()[:max_width]  # Make sure to handle width before quoting.
        if quote:
            value = f'"{value}"'
        return value

    @api.model
    def _get_report_date_to(self, options):
        """
        Return date_to directly from options, previously used date_to to determine end date based on export periodicity.
        Kept the method for stable versions, otherwise safe to remove.
        """
        return fields.Date.from_string(options['date']['date_to'])
