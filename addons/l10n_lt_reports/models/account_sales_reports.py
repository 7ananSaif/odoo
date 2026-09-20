from collections import defaultdict

from odoo import models


class LithuaniaEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_lt.ec.sales.report.handler'
    _inherit = ['account.ec.sales.report.handler']
    _description = 'Lithuanian EC Sales Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        lines = []

        totals_by_column_group = {
            column_group_key: {
                "goods": 0.0,
                "services": 0.0,
                "triangular": 0.0,
                "balance": 0.0,
            }
            for column_group_key in options['column_groups']
        }
        for partner, results in super()._query_partners(report, options):
            partner_values = defaultdict(dict)

            for column_group_key in options['column_groups']:
                partner_sum = results.get(column_group_key, {})
                partner_values[column_group_key]['country_code'] = partner_sum.get('country_code') or 'UNKNOWN'
                partner_values[column_group_key]['vat_number'] = partner_sum.get('vat_number') or ''
                partner_values[column_group_key]['goods'] = goods = partner_sum.get('goods') or 0.0
                partner_values[column_group_key]['services'] = services = partner_sum.get('services') or 0.0
                partner_values[column_group_key]['triangular'] = triangular = partner_sum.get('triangular') or 0.0
                line_balance = goods + services + triangular
                partner_values[column_group_key]['balance'] = line_balance

                totals_by_column_group[column_group_key]['goods'] += goods
                totals_by_column_group[column_group_key]['services'] += services
                totals_by_column_group[column_group_key]['triangular'] += triangular
                totals_by_column_group[column_group_key]['balance'] += line_balance

            lines.append((0, super()._get_report_line_partner(report, options, partner, partner_values)))

        lines.append((0, super()._get_report_line_total(report, options, totals_by_column_group)))
        return lines

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Add custom options for the invoice lines domain specific to Denmark

        Typically, the taxes account.report.expression ids relative to the country for the triangular, sale of goods
        or services.
        """
        super()._custom_options_initializer(report, options, previous_options)

        ec_operation_category = options.get('sales_report_taxes', {})
        ec_operation_category['goods'] = tuple(self.env.ref('l10n_lt.tax_report_line_18_tag')._get_matching_tags().ids)
        ec_operation_category['services'] = tuple(self.env.ref('l10n_lt.tax_report_line_20_eu_tag')._get_matching_tags().ids)
        ec_operation_category['triangular'] = tuple(self.env.ref('l10n_lt.tax_report_line_18_triangular_tag')._get_matching_tags().ids)

        # Unset this as 'use_taxes_instead_of_tags' should never be used outside the generic ec sales report
        ec_operation_category['use_taxes_instead_of_tags'] = False

        options.update({'sales_report_taxes': ec_operation_category})
