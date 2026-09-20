# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import SQL


class L10n_CoIcaReportHandler(models.AbstractModel):
    _name = 'l10n_co.ica.report.handler'
    _inherit = ['l10n_co.report.handler']
    _description = 'ICA Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        domain = self._get_domain(report, options)
        query_results = self._get_query_results(report, options, domain)
        return super()._get_partner_values(report, options, query_results, '_report_expand_unfoldable_line_ica')

    def _get_query_results(self, report, options, domain, expanded=False):
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():

            query = report._get_report_query(column_group_options, 'strict_range', domain=domain)
            bimestre_expression = SQL('FLOOR((EXTRACT(MONTH FROM account_move_line.date) + 1) / 2)')
            ica_type_expression = SQL('account_move_line.name')
            expanded_columns = SQL('%s AS bimestre, %s AS ica_type,', bimestre_expression if expanded else '', ica_type_expression if expanded else '')
            expanded_having = SQL('''
                HAVING SUM(
                    CASE
                    WHEN account_move_line.credit > 0
                        THEN account_move_line.tax_base_amount
                    WHEN account_move_line.debit > 0
                        THEN account_move_line.tax_base_amount * -1
                    ELSE 0
                    END
                ) != 0
            ''') if expanded else SQL()
            queries.append(SQL(
                """
                SELECT
                    %(column_group_key)s AS column_group_key,
                    SUM(account_move_line.credit - account_move_line.debit) AS balance,
                    SUM(CASE
                        WHEN account_move_line.credit > 0
                            THEN account_move_line.tax_base_amount
                        WHEN account_move_line.debit > 0
                            THEN account_move_line.tax_base_amount * -1
                        ELSE 0
                        END
                    ) AS tax_base_amount,
                    %(expanded_columns)s
                    rp.id AS partner_id,
                    rp.name AS partner_name
                FROM %(table_references)s
                JOIN res_partner rp ON account_move_line.partner_id = rp.id
                JOIN account_account aa ON account_move_line.account_id = aa.id
                WHERE %(search_condition)s
                GROUP BY rp.id %(expanded_groupby)s
                %(expanded_having)s
                """,
                column_group_key=column_group_key,
                expanded_columns=expanded_columns,
                table_references=query.from_clause,
                expanded_groupby=SQL(', %s, %s', bimestre_expression, ica_type_expression) if expanded else SQL(),
                search_condition=query.where_clause,
                expanded_having=expanded_having,
            ))

        self.env.cr.execute(SQL(' UNION ALL ').join(queries))
        return self.env.cr.dictfetchall()

    def _get_domain(self, report, options, line_dict_id=None):
        domain = super()._get_domain(report, options, line_dict_id=line_dict_id)
        domain += [('tax_line_id.type_tax_use', '=', 'purchase')]
        # Reports are categorized by the l10n_co_edi_type, which may not be present if l10n_co_edi is uninstalled
        if 'l10n_co_edi_type' in self.env['account.tax']._fields:
            domain += [('tax_line_id.l10n_co_edi_type.code', '=', '07')]
        return domain

    def _report_expand_unfoldable_line_ica(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        report = self.env['account.report'].browse(options['report_id'])
        domain = self._get_domain(report, options, line_dict_id=line_dict_id)
        query_results = self._get_query_results(report, options, domain, expanded=True)
        return super()._get_grouped_values(report, options, query_results, group_by=['bimestre', 'ica_type'])
