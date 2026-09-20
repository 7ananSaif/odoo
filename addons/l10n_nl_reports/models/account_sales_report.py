# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning


class L10n_Nl_ReportsEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_nl_reports.ec.sales.report.handler'
    _inherit = ['account.ec.sales.report.handler']
    _description = 'Dutch EC Sales Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        lines = []

        totals_by_column_group = {
            key: {
                column['expression_label']: 0.0 if column['figure_type'] == 'monetary' else ''
                for column in options['columns']
            } for key in options['column_groups']
        }

        for partner, results in self._query_partners(report, options):
            partner_values = defaultdict(dict)

            for column_group_key in options['column_groups']:
                partner_sum = results.get(column_group_key, {})
                country_code = partner_sum.get('country_code', 'UNKNOWN')

                # For Greece, the ISO 3166 code (GR) and European Union code (EL) is not the same.
                # Since this is a european report, we need the European Union code.
                if country_code == 'GR':
                    country_code = 'EL'

                line_total = partner_sum.get('goods', 0.0) + partner_sum.get('services', 0.0) + partner_sum.get('triangular', 0.0)

                partner_values[column_group_key].update({
                    'country_code': country_code,
                    'partner_name': '',
                    'vat': self._format_vat(partner_sum.get('full_vat_number'), country_code),
                    'amount_product': partner_sum.get('goods', 0.0),
                    'amount_service': partner_sum.get('services', 0.0),
                    'amount_triangular': partner_sum.get('triangular', 0.0),
                    'total': line_total,
                })

                totals_by_column_group[column_group_key]['amount_product'] += partner_sum.get('goods', 0.0)
                totals_by_column_group[column_group_key]['amount_service'] += partner_sum.get('services', 0.0)
                totals_by_column_group[column_group_key]['amount_triangular'] += partner_sum.get('triangular', 0.0)
                totals_by_column_group[column_group_key]['total'] += line_total

            lines.append((0, self._get_report_line_partner(report, options, partner, partner_values)))

        lines.append((0, self._get_report_line_total(report, options, totals_by_column_group)))
        return lines

    def _caret_options_initializer(self):
        """
        Add custom caret option for the report to link to the partner and allow cleaner overrides.
        """
        return {
            'nl_icp_partner': [
                {'name': _("View Partner"), 'action': 'caret_option_open_record_form'},
            ],
        }

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options['buttons'].append({'name': "XBRL", 'sequence': 40, 'action': 'open_xbrl_wizard', 'file_export_type': 'XBRL'})

        goods_tag = self.env.ref('l10n_nl.tax_report_rub_3bg_tag', raise_if_not_found=False)
        services_tag = self.env.ref('l10n_nl.tax_report_rub_3bs_tag', raise_if_not_found=False)
        triangular_tag = self.env.ref('l10n_nl.tax_report_rub_3bt_tag', raise_if_not_found=False)
        if goods_tag and services_tag and triangular_tag:
            options.get('sales_report_taxes', {}).update({
                'goods': goods_tag._get_matching_tags().ids,
                'services': services_tag._get_matching_tags().ids,
                'triangular': triangular_tag._get_matching_tags().ids,
                'use_taxes_instead_of_tags': False,
            })
        else:
            goods_tax = self.env['account.chart.template'].ref('btw_X0_producten', raise_if_not_found=False)
            services_tax = self.env['account.chart.template'].ref('btw_X0_diensten', raise_if_not_found=False)
            triangular_tax = self.env['account.chart.template'].ref('btw_X0_ABC_levering', raise_if_not_found=False)
            options.get('sales_report_taxes', {}).update({
                'goods': [goods_tax.id] if goods_tax else [],
                'services': [services_tax.id] if services_tax else [],
                'triangular': [triangular_tax.id] if triangular_tax else [],
                'use_taxes_instead_of_tags': True,
            })

    @api.model
    def _format_vat(self, vat, country_code):
        """ VAT numbers must be reported without country code, and grouped by 4
        characters, with a space between each pair of groups.
        """
        if vat:
            if vat[:2].lower() == country_code.lower():
                vat = vat[2:]
            return vat
        return None

    def open_xbrl_wizard(self, options):
        res = self.env['l10n_nl_reports.tax.report.handler'].open_xbrl_wizard(options)
        res.update({
            'name': _('EC Sales (ICP) SBR'),
            'res_model': 'l10n_nl_reports.sbr.icp.wizard',
        })
        for ec_tax_filter in res['context']['options']['ec_tax_filter_selection']:
            ec_tax_filter['selected'] = True
        return res

    def export_icp_report_to_xbrl(self, options):
        # This will generate the XBRL file (similar style to XML).
        report = self.env['account.report'].browse(options['report_id'])
        lines = report._get_lines(options)
        data = self._generate_codes_values(report, lines, options)

        date_to = fields.Date.to_date(options['date']['date_to'])
        template_xmlid = 'l10n_nl_reports.icp_report_sbr'
        if date_to.year == 2024:
            # We still need to support the NT18 taxonomy for 2024 until that declaration period is over.
            template_xmlid = 'l10n_nl_reports.icp_report_sbr_nt18'

        report_template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not report_template:
            raise RedirectWarning(
                message=_(
                    "We couldn't find the correct export template for the year %(year)s. Please upgrade your module 'Netherlands - Accounting Reports' and try again.",
                    year=date_to.year,
                ),
                action=self.env.ref('base.open_module_tree').id,
                button_text=_("Go to Apps"),
                additional_context={
                    'search_default_name': 'l10n_nl_reports',
                    'search_default_extra': True,
                },
            )

        xbrl = self.env['ir.qweb']._render(report_template.id, data)
        xbrl_element = etree.fromstring(xbrl)
        xbrl_file = etree.tostring(xbrl_element, xml_declaration=True, encoding='utf-8')
        return {
            'file_name': report.get_default_report_filename(options, 'xbrl'),
            'file_content': xbrl_file,
            'file_type': 'xml',
        }

    def _generate_codes_values(self, report, lines, options):
        codes_values = options.get('codes_values', {})
        codes_values.update({
            'IntraCommunitySupplies': [],
            'IntraCommunityServices': [],
            'IntraCommunityABCSupplies': [],
            'VATIdentificationNumberNLFiscalEntityDivision': self.env.company.vat[2:] if self.env.company.vat.startswith('NL') else self.env.company.vat,
        })

        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        company_currency = self.env.company.currency_id
        for line in lines:
            if report._get_markup(line['id']) != 'total':
                if company_currency.compare_amounts(line['columns'][colname_to_idx['amount_product']].get('no_format', 0), 0):
                    codes_values['IntraCommunitySupplies'].append({
                        'CountryCodeISO': line['columns'][colname_to_idx['country_code']].get('name'),
                        'SuppliesAmount': str(int(line['columns'][colname_to_idx['amount_product']].get('no_format'))),
                        'VATIdentificationNumberNational': line['columns'][colname_to_idx['vat']].get('name'),
                    })
                if company_currency.compare_amounts(line['columns'][colname_to_idx['amount_service']].get('no_format', 0), 0):
                    codes_values['IntraCommunityServices'].append({
                        'CountryCodeISO': line['columns'][colname_to_idx['country_code']].get('name'),
                        'ServicesAmount': str(int(line['columns'][colname_to_idx['amount_service']].get('no_format'))),
                        'VATIdentificationNumberNational': line['columns'][colname_to_idx['vat']].get('name', 0),
                    })
                if company_currency.compare_amounts(line['columns'][colname_to_idx['amount_triangular']].get('no_format', 0), 0):
                    codes_values['IntraCommunityABCSupplies'].append({
                        'CountryCodeISO': line['columns'][colname_to_idx['country_code']].get('name'),
                        'SuppliesAmount': str(int(line['columns'][colname_to_idx['amount_triangular']].get('no_format'))),
                        'VATIdentificationNumberNational': line['columns'][colname_to_idx['vat']].get('name'),
                    })
        return codes_values
