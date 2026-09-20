from datetime import datetime
import json
import re

from lxml import etree

from odoo import fields, models, _
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools.misc import get_lang


PREFIX = 'l10n_be_reports.'
REPORT_MATCHINGS = {
    ((f'{PREFIX}account_financial_report_bs_comp_acon', f'{PREFIX}account_financial_report_pl_comp_a'), f'{PREFIX}xbrl_template_acon'),
    ((f'{PREFIX}account_financial_report_bs_comp_acap', f'{PREFIX}account_financial_report_pl_comp_a'), f'{PREFIX}xbrl_template_acap'),
    ((f'{PREFIX}account_financial_report_bs_comp_fcon', f'{PREFIX}account_financial_report_pl_comp_f'), f'{PREFIX}xbrl_template_fcon'),
    ((f'{PREFIX}account_financial_report_bs_comp_fcap', f'{PREFIX}account_financial_report_pl_comp_f'), f'{PREFIX}xbrl_template_fcap'),
    ((f'{PREFIX}account_financial_report_bs_asso_a', f'{PREFIX}account_financial_report_pl_asso_a'), f'{PREFIX}xbrl_template_asso_a'),
    ((f'{PREFIX}account_financial_report_bs_asso_f', f'{PREFIX}account_financial_report_pl_asso_f'), f'{PREFIX}xbrl_template_asso_f'),
}


class AnnualStatementReportHandler(models.AbstractModel):
    _name = 'annual.statement.report.handler'
    _inherit = ['account.report.custom.handler']
    _description = 'Annual Statement Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if report.country_id.code == 'BE':
            options['buttons'].append({'name': "XBRL", 'sequence': 30, 'action': 'open_xbrl_wizard', 'file_export_type': 'XBRL'})

    def open_xbrl_wizard(self, options):
        return {
            'name': _('XBRL Export'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'l10n_be_reports.xbrl.export.wizard',
            'target': 'new',
            'context': {
                'options': options,
                },
            'views': [[False, 'form']],
        }

    def export_to_xbrl(self, options):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'generate_xbrl_file',
            }
        }

    def generate_xbrl_file(self, options):
        """This will generate the XBRL file (similar style to XML)."""

        def change_options_date(report, options, date_from, date_to):
            options['date'] = report._get_dates_period(
                date_from,
                date_to,
                'range')
            for column_group in options['column_groups'].values():
                if column_group['forced_options'].get('date'):
                    column_group['forced_options']['date'] = options['date']

        report = self.env['account.report'].browse(options['report_id'])
        if report.country_id.code != 'BE':
            raise UserError(_("XBRL export is only applicable for Belgium reports. Please change to Belgium annual statement report."))

        current_fiscal_date = self.env.company.compute_fiscalyear_dates(datetime.strptime(options['date']['date_to'], '%Y-%m-%d'))
        change_options_date(report, options, current_fiscal_date['date_from'], current_fiscal_date['date_to'])

        self._validate_company_data()

        # To extract house number: 2 capture groups, one for number, one for street
        match = re.findall(r'(\b\d+\w*\b)|((?:\b(?!\d)\w+\b(?:\s+|$))+)', self.env.company.street)
        house_number = next((m[0] for m in match if m[0]), None) or '0'
        street = next((m[1] for m in match if m[1]), None) or self.env.company.street

        data = {
            'company_lang': lang if (lang := get_lang(self.env).code.split('_')[0]) in ('fr', 'nl', 'de') else 'en',
            'company_registry': self.env.company.company_registry or self.env.company.vat[2:],
            'date': fields.Date.context_today(self).strftime('%Y-%m-%d'),
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'company_type': "lgf:" + self.env.company.l10n_be_company_type_id.xbrl_code,
            'company_name': self.env.company.name,
            'company_street': street.strip(),
            'company_house_number': house_number,
            'company_postal_code': "pcd:m" + self.env.company.zip,
            'company_region': "cct:" + self.env.company.l10n_be_region_id.xbrl_code,
            'company_country': "cty:mBE",
            'last_deed_date': options.get('last_deed_date'),
        }

        chosen_report_xml_ids = {r.get_external_id().get(r.id) for r in report.section_report_ids}
        chosen_pair = [pair for pair in REPORT_MATCHINGS if chosen_report_xml_ids.issuperset(pair[0])]
        if len(chosen_pair) != 1:
            raise UserError(_("Please add a single balance sheet and a single profit and loss report that have a matching (Abbr or Full) format for the XBRL export."))

        chosen_reports = [r for r in report.section_report_ids if r.get_external_id().get(r.id) in chosen_pair[0][0]]
        for chosen_report in chosen_reports:
            report_options = chosen_report.get_options({})
            change_options_date(chosen_report, report_options, current_fiscal_date['date_from'], current_fiscal_date['date_to'])

            lines = chosen_report._get_lines(report_options)
            for line in lines:
                report_line = self.env['account.report.line'].browse(line['columns'][0]['report_line_id'])
                if report_line.code == 'BE_BS_499':
                    if line['columns'][0]['no_format'] > 0:
                        raise UserError(_("The 499 accounts should always be zero before exporting XBRL. Please correct your accounts and try again."))
                elif report_line.code:
                    data[report_line.code] = round(line['columns'][0]['no_format'], 2)

        data.update(self._get_extra_file_data(options))

        template_xmlid = chosen_pair[0][1]
        report_template = self.env.ref(template_xmlid, raise_if_not_found=False)
        xbrl = self.env['ir.qweb']._render(report_template.id, data)
        xbrl_element = etree.fromstring(xbrl)
        xbrl_file = etree.tostring(xbrl_element, xml_declaration=True, encoding='utf-8')
        return {
            'file_name': report.get_default_report_filename(options, 'xbrl'),
            'file_content': xbrl_file,
            'file_type': 'xml',
        }

    def _get_extra_file_data(self, options):
        """Method to be overridden if some extra data should be passed to the file generator."""
        return {}

    def _validate_company_data(self):
        """Validates that the company has all required data for generating the XBRL file."""

        required_address_fields = ('vat', 'street', 'zip', 'l10n_be_region_id', 'l10n_be_company_type_id')
        missing_fields = []
        for field in required_address_fields:
            if not self.env.company[field]:
                missing_fields.append(self.env['res.company']._fields[field].string)

        if missing_fields:
            field = ', '.join(missing_fields)
            action = {
                'view_mode': 'form',
                'res_model': 'res.company',
                'type': 'ir.actions.act_window',
                'res_id': self.env.company.id,
                'views': [[self.env.ref('base.view_company_form').id, 'form']],
            }
            raise RedirectWarning(
                _("Please fill in the following company data before generating the XBRL file: %s", field),
                action,
                _("Go to company configuration")
            )
