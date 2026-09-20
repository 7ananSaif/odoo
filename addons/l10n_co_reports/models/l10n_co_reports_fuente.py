# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import SQL, get_lang


class L10n_CoFuenteReportHandler(models.AbstractModel):
    _name = 'l10n_co.fuente.report.handler'
    _inherit = ['l10n_co.report.handler']
    _description = 'Fuente Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        domain = self._get_domain(report, options)
        query_results = self._get_query_results(report, options, domain)
        return super()._get_partner_values(report, options, query_results, '_report_expand_unfoldable_line_fuente')

    def _get_query_results(self, report, options, domain, expanded=False):
        queries = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, 'strict_range', domain=domain)
            origin_tax_id_expression = SQL('tax.id')
            lang = self.env.user.lang or get_lang(self.env).code
            origin_tax_desc_expression = SQL("COALESCE(tax.description->>%s,tax.description->>'en_US')", lang)
            origin_tax_desc_expression = SQL("REGEXP_REPLACE(%s, '(<([^>]+)>)', '', 'g')", origin_tax_desc_expression)
            expanded_columns = SQL('%s AS origin_tax_id, %s AS origin_tax_desc,', origin_tax_id_expression if expanded else '', origin_tax_desc_expression if expanded else '')
            tax_base_amount_select = SQL("""
                SUM(CASE
                    WHEN account_move_line.credit > 0
                        THEN account_move_line.tax_base_amount
                    WHEN account_move_line.debit > 0
                        THEN account_move_line.tax_base_amount * -1
                    ELSE 0
                    END)
            """)
            queries.append(SQL(
                """
                SELECT
                    %(column_group_key)s AS column_group_key,
                    SUM(account_move_line.credit - account_move_line.debit) AS balance,
                    %(tax_base_amount_select)s AS tax_base_amount,
                    %(expanded_columns)s
                    rp.id AS partner_id,
                    rp.name AS partner_name
                FROM %(table_references)s
                JOIN res_partner rp ON account_move_line.partner_id = rp.id
                JOIN account_tax tax ON account_move_line.tax_line_id = tax.id
                WHERE %(search_condition)s
                GROUP BY rp.id %(expanded_groupby)s
                %(having_clause)s
                """,
                column_group_key=column_group_key,
                tax_base_amount_select=tax_base_amount_select,
                expanded_columns=expanded_columns,
                table_references=query.from_clause,
                search_condition=query.where_clause,
                expanded_groupby=SQL(', %s', origin_tax_id_expression) if expanded else SQL(),
                having_clause=SQL("HAVING %s != 0", tax_base_amount_select) if expanded else SQL(),
            ))

        self.env.cr.execute(SQL(' UNION ALL ').join(queries))
        return self.env.cr.dictfetchall()

    def _get_domain(self, report, options, line_dict_id=None):
        domain = super()._get_domain(report, options, line_dict_id=line_dict_id)
        domain += [('tax_line_id.type_tax_use', '=', 'purchase')]
        # Reports are categorized by the l10n_co_edi_type, which may not be present if l10n_co_edi is uninstalled
        if 'l10n_co_edi_type' in self.env['account.tax']._fields:
            domain += [('tax_line_id.l10n_co_edi_type.code', '=', '06')]
        return domain

    def _report_expand_unfoldable_line_fuente(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        report = self.env['account.report'].browse(options['report_id'])
        domain = self._get_domain(report, options, line_dict_id=line_dict_id)
        query_results = self._get_query_results(report, options, domain, expanded=True)
        return super()._get_grouped_values(report, options, query_results, group_by=['origin_tax_id'])
