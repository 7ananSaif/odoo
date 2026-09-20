import datetime

from lxml import etree

from odoo import _, fields, models
from odoo.exceptions import RedirectWarning, UserError


class L10n_Nl_ReportsTaxReportHandler(models.AbstractModel):
    _name = 'l10n_nl_reports.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Dutch Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['buttons'].append({'name': "XBRL", 'sequence': 30, 'action': 'open_xbrl_wizard', 'file_export_type': 'XBRL'})
        options['l10n_nl_is_correction'] = previous_options.get('l10n_nl_is_correction', False)
        options['return_id'] = previous_options.get('return_id', False)

    def open_xbrl_wizard(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        if report.filter_multi_company != 'tax_units' and len(options['companies']) > 1:
            raise UserError(_('Please select only one company to send the report. If you wish to aggregate multiple companies, please create a tax unit.'))
        date_to = datetime.date.fromisoformat(options['date']['date_to'])
        closing_date_from, closing_date_to = self.env.ref('l10n_nl_reports.nl_tax_return_type')._get_period_boundaries(self.env.company, date_to)
        new_options = report.get_options({
            **options,
            'date': {
                'date_from': closing_date_from,
                'date_to': closing_date_to,
                'mode': 'range',
                'filter': 'custom',
            },
            'integer_rounding_enabled': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Report SBR'),
            'view_mode': 'form',
            'res_model': 'l10n_nl_reports.sbr.tax.report.wizard',
            'target': 'new',
            'context': {
                'options': new_options,
                'default_date_from': closing_date_from,
                'default_date_to': closing_date_to,
                },
            'views': [[False, 'form']],
        }

    def export_tax_report_to_xbrl(self, options):
        # This will generate the XBRL file (similar style to XML).
        report = self.env['account.report'].browse(options['report_id'])
        lines = report._get_lines(options)
        data = self._generate_codes_values(lines, options)

        date_to = fields.Date.to_date(options['date']['date_to'])
        if options['l10n_nl_is_correction']:
            template_xmlid = 'l10n_nl_reports.suppletie_tax_report_sbr'
        else:
            template_xmlid = 'l10n_nl_reports.tax_report_sbr'
            if date_to.year == 2024:
                # We still need to support the NT18 taxonomy for 2024 until that declaration period is over.
                template_xmlid = 'l10n_nl_reports.tax_report_sbr_nt18'

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
        xbrl_file_name = report.get_default_report_filename(options, 'xbrl')
        if options['l10n_nl_is_correction']:
            xbrl_file_name = xbrl_file_name.replace('.xbrl', '_suppletie.xbrl')
        return {
            'file_name': xbrl_file_name,
            'file_content': xbrl_file,
            'file_type': 'xml',
        }

    def _generate_codes_values(self, lines, options):
        codes_values = options.get('codes_values', {})
        # Maps the needed taxes to their codewords used by the XBRL template.
        tax_report_lines_to_codes = {
            'l10n_nl.tax_report_rub_3c': [('InstallationDistanceSalesWithinTheEC', 'base')],
            'l10n_nl.tax_report_rub_1e': [('SuppliesServicesNotTaxed', 'base')],
            'l10n_nl.tax_report_rub_3a': [('SuppliesToCountriesOutsideTheEC', 'base')],
            'l10n_nl.tax_report_rub_3b': [('SuppliesToCountriesWithinTheEC', 'base')],
            'l10n_nl.tax_report_rub_1d': [('TaxedTurnoverPrivateUse', 'base'), ('ValueAddedTaxPrivateUse', 'tax')],
            'l10n_nl.tax_report_rub_1a': [('TaxedTurnoverSuppliesServicesGeneralTariff', 'base'), ('ValueAddedTaxSuppliesServicesGeneralTariff', 'tax')],
            'l10n_nl.tax_report_rub_1c': [('TaxedTurnoverSuppliesServicesOtherRates', 'base'), ('ValueAddedTaxSuppliesServicesOtherRates', 'tax')],
            'l10n_nl.tax_report_rub_1b': [('TaxedTurnoverSuppliesServicesReducedTariff', 'base'), ('ValueAddedTaxSuppliesServicesReducedTariff', 'tax')],
            'l10n_nl.tax_report_rub_4a': [('TurnoverFromTaxedSuppliesFromCountriesOutsideTheEC', 'base'), ('ValueAddedTaxOnSuppliesFromCountriesOutsideTheEC', 'tax')],
            'l10n_nl.tax_report_rub_4b': [('TurnoverFromTaxedSuppliesFromCountriesWithinTheEC', 'base'), ('ValueAddedTaxOnSuppliesFromCountriesWithinTheEC', 'tax')],
            'l10n_nl.tax_report_rub_2a': [('TurnoverSuppliesServicesByWhichVATTaxationIsTransferred', 'base'), ('ValueAddedTaxSuppliesServicesByWhichVATTaxationIsTransferred', 'tax')],
            'l10n_nl.tax_report_rub_btw_5b': [('ValueAddedTaxOnInput', 'tax')],
            'l10n_nl.tax_report_rub_btw_5a': [('ValueAddedTaxOwed', 'tax')],
            'l10n_nl.tax_report_rub_btw_5g': [('ValueAddedTaxOwedToBePaidBack', 'tax')],
        }
        if options['l10n_nl_is_correction']:
            tax_report_lines_to_codes.update({
                'l10n_nl.tax_report_rub_btw_5e': [('ValueAddedTaxAmountTotalNew', 'tax')],
                'l10n_nl.tax_report_rub_btw_5f': [('ValueAddedTaxAmountTotalOld', 'tax')],
                'l10n_nl.tax_report_rub_btw_5g': [('ValueAddedTaxToBePaidAdditionalToBePaidBack', 'tax')],
            })

        model_trl_to_codes = {}
        for tax_report_line_id, codes in tax_report_lines_to_codes.items():
            model_trl_to_codes[self.env.ref(tax_report_line_id).id] = codes

        for line in lines:
            codes = model_trl_to_codes.get(self.env['account.report']._get_model_info_from_id(line['id'])[1]) or []
            for code, label in codes:
                codes_values[code] = str(int(next(col for col in line['columns'] if col['expression_label'] == label)['no_format']))
        return codes_values

    def _custom_line_postprocessor(self, report, options, lines):
        if not options['l10n_nl_is_correction']:
            return lines

        # If we are constructing a corrective VAT declaration (suppletie), we need to modify the last 3 lines:
        # - 5e gets the values of 5g (computed result of this declaration)
        # - 5f is a new line indicating the previous declaration(s) amount
        # - 5g is a new line computing the difference between the new 5e and 5f (amount still to pay or reclaim)

        line_5e = self.env.ref('l10n_nl.tax_report_rub_btw_5e')
        line_5f = self.env.ref('l10n_nl.tax_report_rub_btw_5f')
        line_5g = self.env.ref('l10n_nl.tax_report_rub_btw_5g')
        new_line_5e_dict, new_line_5f_dict, new_line_5g_dict = {}, {}, {}

        new_lines = []
        # Intercept lines to modify and prepare their values.
        for line in lines:
            line_record_id = report._get_res_id_from_line_id(line['id'], 'account.report.line')
            match line_record_id:
                case line_5e.id:
                    new_line_5e_dict.update({
                        'id': line['id'],
                        'name': self.env._("5e. End total"),
                        'parent_id': line['parent_id'],
                        'level': line['level'],
                    })
                case line_5f.id:
                    new_line_5f_dict.update({
                        'id': line['id'],
                        'name': self.env._("5f. Balance already declared amount"),
                        'parent_id': line['parent_id'],
                        'level': line['level'],
                        'columns': [{**col} for col in line['columns']],  # Deep copy of the columns
                    })
                case line_5g.id:
                    new_line_5g_dict.update({
                        'id': line['id'],
                        'name': line['name'],
                        'parent_id': line['parent_id'],
                        'level': line['level'],
                        'columns': [{**col} for col in line['columns']],  # Deep copy of the columns
                    })
                    new_line_5e_dict.update({
                        'debug_popup_data': line.get('debug_popup_data'),
                        'columns': [{**col} for col in line['columns']],  # Deep copy of the columns
                    })
                case _:
                    new_lines.append(line)

        return_generic_domain = [
            ('company_id', '=', report._get_sender_company_for_export(options).id),
            ('type_id', 'in', (
                self.env.ref('l10n_nl_reports.nl_tax_return_type').id,
                self.env.ref('l10n_nl_reports.nl_tax_correction_return_type').id,
            )),
            ('id', '!=', options['return_id']),
        ]

        # Fill the values in the columns for the new lines.
        for i, column in enumerate(options['columns']):
            if column['expression_label'] != 'tax':
                continue

            column_date = options['column_groups'][column['column_group_key']]['forced_options']['date']
            previous_returns_result = sum(self.env['account.return'].search([
                *return_generic_domain,
                ('date_from', '=', column_date['date_from']),
                ('date_to', '=', column_date['date_to']),
            ]).mapped('period_amount_to_pay'))
            amount_payable_reclaimable = new_line_5e_dict['columns'][i]['no_format'] - previous_returns_result
            new_line_5f_dict['columns'][i].update({
                'auditable': False,
                'is_zero': self.env.company.currency_id.is_zero(previous_returns_result),
                'no_format': previous_returns_result,
                'report_line_id': None,
            })
            new_line_5g_dict['columns'][i].update({
                'auditable': False,
                'is_zero': self.env.company.currency_id.is_zero(amount_payable_reclaimable),
                'no_format': amount_payable_reclaimable,
                'report_line_id': None,
            })

        new_lines.extend([new_line_5e_dict, new_line_5f_dict, new_line_5g_dict])

        return new_lines
