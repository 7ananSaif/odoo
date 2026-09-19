# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io
from collections import defaultdict

import logging
from datetime import datetime
import re
import xlsxwriter

from odoo import api, models, _
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _init_options_buttons(self, options, previous_options):
        super()._init_options_buttons(options, previous_options)
        company = self.env.company
        gstr2b_report = self.env.ref('l10n_in_reports.account_report_gstr2b').id

        # Remove 'Returns' button if company is Indian and eFiling is disabled
        if company.country_id.code == 'IN' and not self.env.company.l10n_in_gst_efiling_feature:
            options['buttons'] = [
                button for button in options['buttons']
                if button.get('action') != 'action_open_returns'
            ]
        if gstr2b_report == options['report_id']:
            for button in options['buttons']:
                if button.get('action') == 'action_open_returns':
                    button['name'] = 'Reconcile'


class L10n_InReportHandler(models.AbstractModel):
    _name = 'l10n_in.report.handler'
    _inherit = ['account.generic.tax.report.handler']
    _description = 'Indian Tax Report Custom Handler'

    @api.model
    def _get_invalid_intra_state_tax_on_lines(self, aml_domain):
        intra_state_sgst_cgst = self.env['account.move.line'].search(
            aml_domain +
            [
                ('move_id.l10n_in_transaction_type', '=', 'intra_state'),
                ('tax_tag_ids', 'in', self.env.ref('l10n_in.tax_tag_base_igst').id),
                ('move_id.l10n_in_gst_treatment', '!=', 'special_economic_zone')
            ]
        )
        return 'l10n_in_reports.invalid_intra_state_warning', intra_state_sgst_cgst

    @api.model
    def _get_invalid_inter_state_tax_on_lines(self, aml_domain):
        inter_state_igst = self.env['account.move.line'].search(
            aml_domain +
            [
                ('move_id.l10n_in_transaction_type', '=', 'inter_state'),
                ('tax_tag_ids', 'in', (self.env.ref('l10n_in.tax_tag_base_cgst').id, self.env.ref('l10n_in.tax_tag_base_sgst').id)),
            ]
        )
        return 'l10n_in_reports.invalid_inter_state_warning', inter_state_igst

    def _get_invalid_no_hsn_line_domain(self):
        return [
            ('l10n_in_gstr_section', '!=', 'sale_out_of_scope'),
            ('l10n_in_hsn_code', '=', False),
            ('display_type', '!=', 'tax')
        ]

    @api.model
    def _get_invalid_no_hsn_products(self, aml_domain):
        missing_hsn = self.env['account.move.line'].search(
            aml_domain + self._get_invalid_no_hsn_line_domain()
        )
        return 'l10n_in_reports.missing_hsn_warning', missing_hsn

    @api.model
    def _get_invalid_uqc_codes(self, aml_domain):
        uqc_codes = [
            'BAG-BAGS',
            'BAL-BALE',
            'BDL-BUNDLES',
            'BKL-BUCKLES',
            'BOU-BILLION OF UNITS',
            'BOX-BOX',
            'BTL-BOTTLES',
            'BUN-BUNCHES',
            'CAN-CANS',
            'CBM-CUBIC METERS',
            'CCM-CUBIC CENTIMETERS',
            'CMS-CENTIMETERS',
            'CTN-CARTONS',
            'DOZ-DOZENS',
            'DRM-DRUMS',
            'GGK-GREAT GROSS',
            'GMS-GRAMMES',
            'GRS-GROSS',
            'GYD-GROSS YARDS',
            'KGS-KILOGRAMS',
            'KLR-KILOLITRE',
            'KME-KILOMETRE',
            'LTR-LITRES',
            'MLT-MILILITRE',
            'MTR-METERS',
            'MTS-METRIC TON',
            'NOS-NUMBERS',
            'PAC-PACKS',
            'PCS-PIECES',
            'PRS-PAIRS',
            'QTL-QUINTAL',
            'ROL-ROLLS',
            'SET-SETS',
            'SQF-SQUARE FEET',
            'SQM-SQUARE METERS',
            'SQY-SQUARE YARDS',
            'TBS-TABLETS',
            'TGM-TEN GROSS',
            'THD-THOUSANDS',
            'TON-TONNES',
            'TUB-TUBES',
            'UGS-US GALLONS',
            'UNT-UNITS',
            'YDS-YARDS',
            'OTH-OTHERS',
        ]
        domain = aml_domain + [
                    ('l10n_in_gstr_section', '!=', 'sale_out_of_scope'),
                    ('product_id.l10n_in_hsn_code', 'not =ilike', '99%'),
                    ('product_id.uom_id.l10n_in_code', 'not in', uqc_codes),
                ]
        invalid_uqc_codes = self.env['account.move.line'].search(domain).product_id.uom_id
        return 'l10n_in_reports.invalid_uqc_code_warning', invalid_uqc_codes

    def _get_reversed_moves_domain(self, options):
        return [
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            '|',
            ('line_ids.tax_ids.l10n_in_tax_type', 'in', ['gst', 'nil_rated', 'exempt', 'non_gst']),
            ('line_ids.tax_line_id.l10n_in_tax_type', 'in', ['gst', 'nil_rated', 'exempt', 'non_gst'])
        ]

    @api.model
    def _get_out_of_fiscal_year_reversed_moves(self, options):
        AccountMove = self.env['account.move']
        out_of_fiscal_year_reversed_moves = AccountMove.search(
            self._get_reversed_moves_domain(options) +
            [
                ('reversed_entry_id', '!=', False),
                ('reversed_entry_id.invoice_date', '<', AccountMove._l10n_in_get_fiscal_year_start_date(self.env.company, datetime.strptime(options['date']['date_to'], '%Y-%m-%d')))
            ]
        )
        return 'l10n_in_reports.out_of_fiscal_year_reversed_moves_warning', out_of_fiscal_year_reversed_moves

    @api.model
    def _get_unlinked_unregistered_inter_state_reversed_moves(self, options):
        unlinked_reversed_moves = self.env['account.move'].search(
            self._get_reversed_moves_domain(options) +
            [
                ('reversed_entry_id', '=', False),
                ('l10n_in_gst_treatment', 'in', ['unregistered', 'consumer']),
                ('l10n_in_transaction_type', '=', 'inter_state'),
            ]
        )
        return 'l10n_in_reports.unlinked_reversed_moves_warning', unlinked_reversed_moves

    @api.model
    def _get_invalid_tds_tcs_moves(self, options, report):
        AccountMove = self.env['account.move']
        domain = [
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('state', '=', 'posted'),
            ('commercial_partner_id.l10n_in_pan_entity_id', '=', False),
        ]
        invalid_move_ids = []
        if report.id == self.env.ref("l10n_in.tds_report").id:
            domain += [('invoice_line_ids.tax_ids.l10n_in_tax_type', '=', 'tds_purchase')]
            invalid_move_ids = AccountMove.search(domain).l10n_in_withholding_ref_move_id.ids
        if report.id == self.env.ref("l10n_in.tcs_report").id:
            domain += [('invoice_line_ids.tax_ids.l10n_in_tax_type', '=', 'tcs')]
            invalid_move_ids = AccountMove.search(domain).ids
        return 'l10n_in_reports.missing_pan_tds_tcs_warning', invalid_move_ids

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        if warnings is not None:
            hsn_base_line_domain = [
                ('l10n_in_gstr_section', '=like', 'sale%'),
                ('display_type', '=', 'product'),
            ]

            options_domain = report._get_options_domain(options, date_scope='strict_range')

            aml_domain = Domain.AND([
                options_domain,
                hsn_base_line_domain,
            ])
            all_checks = []
            if report.id == self.env.ref("l10n_in_reports.account_report_gstr1").id:
                all_checks = [
                    self._get_invalid_intra_state_tax_on_lines(aml_domain),
                    self._get_invalid_inter_state_tax_on_lines(aml_domain),
                    self._get_invalid_no_hsn_products(aml_domain),
                    self._get_invalid_uqc_codes(aml_domain),
                    self._get_out_of_fiscal_year_reversed_moves(options),
                    self._get_unlinked_unregistered_inter_state_reversed_moves(options),
                ]
                all_checks = [
                    (xml_id, obj.ids)
                    for xml_id, obj in all_checks
                ]
            elif report.id in (self.env.ref("l10n_in.tds_report").id, self.env.ref("l10n_in.tcs_report").id):
                all_checks = [
                    self._get_invalid_tds_tcs_moves(options, report),
                ]

            for warning_template_ref, wrong_data in all_checks:
                if wrong_data:
                    warnings[warning_template_ref] = {'ids': wrong_data, 'alert_type': 'warning'}
        return []

    def _l10n_in_open_action(self, name, res_model, views, params):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'views': views,
            'domain': [('id', 'in', params['ids'])],
            'context': {
                'create': False,
                'delete': False,
                'expand': True,
            },
        }

    @api.model
    def open_invalid_intra_state_lines(self, options, params):
        return self._l10n_in_open_action(_('Invalid tax for Intra State Transaction'), 'account.move.line', [(False, 'list')], params)

    @api.model
    def open_invalid_inter_state_lines(self, options, params):
        return self._l10n_in_open_action(_('Invalid tax for Inter State Transaction'), 'account.move.line', [(False, 'list')], params)

    @api.model
    def open_missing_hsn_products(self, options, params):
        return self._l10n_in_open_action(_('Missing HSN for Journal Items'), 'account.move.line', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_invalid_uqc_codes(self, options, params):
        return self._l10n_in_open_action(_('Invalid UQC Code'), 'uom.uom', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_out_of_fiscal_year_reversed_moves(self, options, params):
        return self._l10n_in_open_action(_('Credit Notes'), 'account.move', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_unlinked_reversed_moves(self, options, params):
        return self._l10n_in_open_action(_('Unlinked Credit Notes'), 'account.move', [(False, 'list'), (False, 'form')], params)

    @api.model
    def open_missing_pan_tds_tcs_moves(self, options, params):
        return self._l10n_in_open_action(_('Journal Entries'), 'account.move', [(False, 'list'), (False, 'form')], params)

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        if self.env.company.account_fiscal_country_id.code != 'IN':
            return
        if report in (self.env.ref('l10n_in.tds_report'), self.env.ref('l10n_in.tcs_report')):
            xlsx_button_option = next(button_opt for button_opt in options['buttons'] if button_opt.get('action_param') == 'export_to_xlsx')
            xlsx_button_option['action_param'] = 'tds_tcs_export_to_xlsx'

    @api.model
    def tds_tcs_export_to_xlsx(self, options):
        is_tds_report = options['report_id'] == self.env.ref('l10n_in.tds_report').id
        with io.BytesIO() as output:
            with xlsxwriter.Workbook(output, {
                'in_memory': True,
                'strings_to_formulas': False,
            }) as workbook:
                self._tds_tcs_inject_report_into_xlsx_sheet(options, workbook, is_tds_report)
            report_period = options['date']['string']
            file_name = f"{re.sub(r'[^a-z0-9_]', '', report_period.lower().replace(' - ', '_').replace(' ', '_'))}_{'tds' if is_tds_report else 'tcs'}_report.xlsx"
            return {
                'file_name': file_name,
                'file_content': output.getvalue(),
                'file_type': 'xlsx',
            }

    @api.model
    def _tds_tcs_inject_report_into_xlsx_sheet(self, options, workbook, is_tds_report):
        def write_header(sheet, header):
            for i, val in enumerate(header):
                sheet.write(i, 0, val, title_style)

        def write_rows(sheet, start_row, rows, style_func):
            for i, row in enumerate(rows):
                style = style_func(i)
                for j, val in enumerate(row):
                    sheet.write(start_row + i, j, val, style)

        report = self.env['account.report'].browse(options['report_id'])
        company_name = self.env.company.name
        report_date = options['date']['string']

        title_style = workbook.add_format({'bold': True, 'font_name': 'Arial'})
        line_style = workbook.add_format({'font_name': 'Arial', 'font_size': 11, 'align': 'left'})

        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        lines_mapping = {
            line['name']: ("{:.2f}".format(float(line['columns'][colname_to_idx['balance']]['no_format'])))
            for line in report._get_lines(options)
        }

        # Add Summary Sheet
        summary_sheet = workbook.add_worksheet('Summary')
        summary_sheet.set_column(0, 0, 60)
        summary_sheet.set_column(1, 1, 15)
        write_header(summary_sheet, [report_date, company_name])

        summary_rows = [[name, balance] for name, balance in lines_mapping.items()]
        summary_rows.insert(0, ['Section', 'Balance'])
        write_rows(summary_sheet, 3, summary_rows, lambda i: title_style if i == 0 else line_style)

        # Add Section Sheets
        section_data = self._prepare_tds_tcs_report_data(options, is_tds_report)
        col_widths = [16, 20, 18, 15, 12, 16, 16, 10]
        if is_tds_report:
            col_widths.insert(2, 18)
            col_widths.insert(4, 22)
            col_widths.insert(5, 15)
        for section_name, section_info in section_data.items():
            sheet = workbook.add_worksheet(section_name)
            for i, width in enumerate(col_widths):
                sheet.set_column(i, i, width)
            write_header(sheet, [report_date, next(iter(section_info['description'].values()))])
            write_rows(sheet, 3, section_info['moves'], lambda i: title_style if i == 0 else line_style)

    @api.model
    def _prepare_tds_tcs_report_data(self, options, is_tds_report):
        columns = [
            _("PAN"),
            _("Customer"),
            _("Bill") if is_tds_report else _("Journal Entry"),
            _("Payment Date"),
            _("Amount"),
            _("TDS Debit Amount") if is_tds_report else _("TCS Debit Amount"),
            _("TDS Credit Amount") if is_tds_report else _("TCS Credit Amount"),
            _("TDS Rate") if is_tds_report else _("TCS Rate"),
        ]

        domain = [
            ('date', '>=', options['date']['date_from']),
            ('date', '<=', options['date']['date_to']),
            ('state', '=', 'posted'),
            ('line_ids.display_type', '=', 'tax'),
            ('line_ids.tax_ids.l10n_in_tax_type', '=', 'tds_purchase' if is_tds_report else 'tcs'),
        ]

        query = self.env['account.move']._search(domain)
        # common joins
        query.join('account_move', 'id', 'account_move_line', 'move_id', 'aml')
        query.join('account_move__aml', 'tax_line_id', 'account_tax', 'id', 'tax')
        query.join('account_move__aml__tax', 'l10n_in_section_id', 'l10n_in_section_alert', 'id', 'section')
        query.join('account_move__aml__tax__section', 'tax_report_line_id', 'account_report_line', 'id', 'report_line')

        common_cols = [
            'account_move__aml__tax__section.name AS section_name',
            'account_move__aml__tax__section__report_line.name AS section_description',
            'COALESCE(account_move__aml.debit, 0) AS tax_debit_amount',
            'COALESCE(account_move__aml.credit, 0) AS tax_credit_amount',
            'COALESCE(account_move__aml.tax_base_amount, 0) AS amount',
        ]

        if is_tds_report:
            columns.insert(2, _("Journal Entry"))
            columns.insert(4, _("Bill Ref. (Supplier Inv. No.)"))
            columns.insert(5, _("Deduction Date"))

            query.left_join('account_move', 'l10n_in_withholding_ref_move_id', 'account_move', 'id', 'bill_move')
            query.left_join('account_move__bill_move', 'partner_id', 'res_partner', 'id', 'partner')
            query.left_join('account_move__bill_move__partner', 'l10n_in_pan_entity_id', 'l10n_in_pan_entity', 'id', 'pan_entity')

            qu = query.select(
                *common_cols,
                'account_move__bill_move__partner__pan_entity.name AS partner_pan',
                'account_move__bill_move__partner.name AS partner_name',
                'account_move.name AS wh_move_name',
                'account_move__bill_move.name AS move_name',
                'account_move__bill_move.invoice_date',
                'account_move__bill_move.ref AS bill_ref',
                'ABS(account_move__aml__tax.amount) AS tax_rate',
                'account_move.date AS deduction_date',
            )
        else:
            query.left_join('account_move', 'partner_id', 'res_partner', 'id', 'partner')
            query.left_join('account_move__partner', 'l10n_in_pan_entity_id', 'l10n_in_pan_entity', 'id', 'pan_entity')

            qu = query.select(
                *common_cols,
                'account_move__partner__pan_entity.name AS partner_pan',
                'account_move__partner.name AS partner_name',
                'account_move.name AS move_name',
                'account_move.invoice_date',
                'account_move__aml__tax.amount AS tax_rate',
            )

        self.env.cr.execute(qu)
        rows = self.env.cr.dictfetchall()

        section_data = defaultdict(lambda: {'description': '', 'moves': []})
        for row in rows:
            section = row['section_name']
            section_data[section]['description'] = row['section_description']
            if not section_data[section]['moves']:
                section_data[section]['moves'].append(columns)

            line = [
                row['partner_pan'] or '',
                row['partner_name'] or '',
                row['move_name'] or '',
                row['invoice_date'].strftime("%d/%m/%y") if row['invoice_date'] else '',
                f"{row['amount']:.2f}",
                f"{row['tax_debit_amount']:.2f}",
                f"{row['tax_credit_amount']:.2f}",
                f"{row['tax_rate']}%",
            ]
            if is_tds_report:
                line.insert(2, row['wh_move_name'])
                line.insert(4, row['bill_ref'])
                line.insert(5, row['deduction_date'].strftime("%d/%m/%y") if row['deduction_date'] else '')
            section_data[section]['moves'].append(line)

        return section_data
