# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import calendar
import re
import stdnum

from markupsafe import Markup

from odoo import models, _
from odoo.exceptions import RedirectWarning, UserError


def _raw_phonenumber(phonenumber):
    return re.sub("[^+0-9]", "", phonenumber)[:20]

def _split_vat_number_and_country_code(vat_number):
    """
    Even with base_vat, the vat number doesn't necessarily starts
    with the country code
    We should make sure the vat is set with the country code
    to avoid submitting a declaration with a wrong vat number
    """
    vat_number = vat_number.replace(' ', '').upper()
    try:
        int(vat_number[:2])
        country_code = None
    except ValueError:
        country_code = vat_number[:2]
        vat_number = vat_number[2:]

    return vat_number, country_code

def _get_xml_export_representative_node(report):
    """ The <Representative> node is common to XML exports made for VAT Listing, VAT Intra,
    and tax declaration. It is used in case the company isn't submitting its report directly,
    but through an external accountant.

    :return: The string containing the complete <Representative> node or an empty string,
             in case no representative has been configured.
    """
    representative = report.env.company.account_representative_id
    if representative:
        vat_no, country_from_vat = _split_vat_number_and_country_code(representative.vat or "")
        country = report.env['res.country'].search([('code', '=', country_from_vat)], limit=1)
        phone = representative.phone or ''
        node_values = {
            'vat': stdnum.get_cc_module('be', 'vat').compact(vat_no),   # Sanitize VAT number
            'name': representative.name,
            'street': "%s %s" % (representative.street or "", representative.street2 or ""),
            'zip': representative.zip,
            'city': representative.city,
            'country_code': (country or representative.country_id).code,
            'email': representative.email,
            'phone': _raw_phonenumber(phone)
        }

        missing_fields = [k for k, v in node_values.items() if not v or v == ' ']
        if missing_fields:
            message = _('Some fields required for the export are missing. Please specify them.')
            action = {
                'name': _("Company: %s", representative.name),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'res.partner',
                'views': [[False, 'form']],
                'target': 'new',
                'res_id': representative.id,
                'context': {'create': False},
            }
            button_text = _('Specify')
            additional_context = {'required_fields': missing_fields}
            raise RedirectWarning(message, action, button_text, additional_context)

        return Markup("""<ns2:Representative>
    <RepresentativeID identificationType="NVAT" issuedBy="%(country_code)s">%(vat)s</RepresentativeID>
    <Name>%(name)s</Name>
    <Street>%(street)s</Street>
    <PostCode>%(zip)s</PostCode>
    <City>%(city)s</City>
    <CountryCode>%(country_code)s</CountryCode>
    <EmailAddress>%(email)s</EmailAddress>
    <Phone>%(phone)s</Phone>
</ns2:Representative>""") % node_values

    return Markup()


class L10n_BeTaxReportHandler(models.AbstractModel):
    _name = 'l10n_be.tax.report.handler'
    _inherit = ['account.tax.report.handler']
    _description = 'Belgian Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Export options set by the return submission wizard ; we need them here so that they're not reset in
        # the pdf generation, when calling _get_options()
        options.update({
            'l10n_be_closing_vat_return': previous_options.get('l10n_be_closing_vat_return'),
            'closing_entry': previous_options.get('closing_entry'),
            'ask_restitution': previous_options.get('ask_restitution'),
            'client_nihil': previous_options.get('client_nihil'),
        })

        options['custom_display_config']['pdf_export'] = {'pdf_export_filters': 'l10n_be_reports.pdf_export_filters'}

    def open_account_report_sales(self, options):
        action = self.env['ir.actions.actions']._for_xml_id('account_reports.action_account_report_sales')
        action['params'] = {
            'options': options,
            'ignore_session': True,
        }

        return action

    def export_tax_report_to_xml(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        vat_no, country_from_vat = _split_vat_number_and_country_code(report.get_vat_for_export(options))
        sender_company = report._get_sender_company_for_export(options)
        default_address = sender_company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default")) or sender_company.partner_id

        if not address.email:
            raise UserError(_('No email address associated with company %s.', sender_company.name))

        if not address.phone:
            raise UserError(_('No phone associated with company %s.', sender_company.name))

        # Compute xml
        issued_by = vat_no
        dt_from = options['date'].get('date_from')
        dt_to = options['date'].get('date_to')
        send_ref = str(sender_company.partner_id.id) + str(dt_from[5:7]) + str(dt_to[:4])
        starting_month = dt_from[5:7]
        ending_month = dt_to[5:7]
        quarter = str(((int(starting_month) - 1) // 3) + 1)

        date_from = dt_from[0:7] + '-01'
        date_to = dt_to[0:7] + '-' + str(calendar.monthrange(int(dt_to[0:4]), int(ending_month))[1])

        deduction_text = self._get_deduction_text(options)

        complete_vat = (country_from_vat or (address.country_id and address.country_id.code or "")) + vat_no
        file_data = {
            'issued_by': issued_by,
            'vat_no': complete_vat,
            'only_vat': vat_no,
            # Company name can contain only latin characters
            'company_name': sender_company.name,
            'address': "%s %s" % (address.street or "", address.street2 or ""),
            'post_code': address.zip or "",
            'city': address.city or "",
            'country_code': address.country_id and address.country_id.code or "",
            'email': address.email or "",
            'phone': _raw_phonenumber(address.phone),
            'send_ref': send_ref,
            'quarter': quarter,
            'month': starting_month,
            'year': str(dt_to[:4]),
            'client_nihil': options.get('client_nihil', False) and 'YES' or 'NO',
            'ask_restitution': options.get('ask_restitution', False) and 'YES' or 'NO',
            'comment': options.get('comment'),
            'prorata_deduction': deduction_text,
            'representative_node': _get_xml_export_representative_node(report),
            'rectification_ref': options.get('rectification_ref'),
        }

        rslt = Markup(f"""<?xml version="1.0"?>
<ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
    %(representative_node)s
    <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%(send_ref)s">""") % file_data

        if file_data.get('rectification_ref'):
            rslt += Markup("""
        <ns2:ReplacedVATDeclaration>%(rectification_ref)s</ns2:ReplacedVATDeclaration>
            """) % file_data

        rslt += Markup(f"""<ns2:Declarant>
            <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">%(only_vat)s</VATNumber>
            <Name>%(company_name)s</Name>
            <Street>%(address)s</Street>
            <PostCode>%(post_code)s</PostCode>
            <City>%(city)s</City>
            <CountryCode>%(country_code)s</CountryCode>
            <EmailAddress>%(email)s</EmailAddress>
            <Phone>%(phone)s</Phone>
        </ns2:Declarant>
        <ns2:Period>
            {"<ns2:Quarter>%(quarter)s</ns2:Quarter>" if starting_month != ending_month else "<ns2:Month>%(month)s</ns2:Month>"}
            <ns2:Year>%(year)s</ns2:Year>
        </ns2:Period>
        %(prorata_deduction)s
        <ns2:Data>""") % file_data

        grids_list = []
        currency_id = self.env.company.currency_id

        options = report.get_options({'no_format': True, 'date': {'date_from': date_from, 'date_to': date_to}, 'filter_unfold_all': True, 'export_mode': 'file'})
        lines = report._get_lines(options)

        # Create a mapping between report line ids and actual grid names
        non_compound_rep_lines = report.line_ids.expression_ids.filtered(
                lambda x: x.formula not in {'48s44', '48s46L', '48s46T', '-46L', '-46T'})
        lines_grids_map = {
            expr.report_line_id.id: expr.formula.split('.')[0].replace('c', '') for expr in non_compound_rep_lines
        }
        lines_grids_map[self.env.ref('l10n_be.tax_report_title_operations_sortie_46').id] = '46'
        lines_grids_map[self.env.ref('l10n_be.tax_report_title_operations_sortie_48').id] = '48'
        lines_grids_map[self.env.ref('l10n_be.tax_report_line_71').id] = '71'
        lines_grids_map[self.env.ref('l10n_be.tax_report_line_72').id] = '72'
        colname_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}

        # Iterate on the report lines, using this mapping
        for line in lines:
            model, line_id = report._parse_line_id(line['id'])[-1][1:]
            if (
                    model == 'account.report.line'
                    and line_id in lines_grids_map
                    and not currency_id.is_zero(line['columns'][colname_to_idx['balance']]['no_format'])
            ):
                grids_list.append((lines_grids_map[line_id].lstrip('-'),
                                   line['columns'][colname_to_idx['balance']]['no_format'],
                                   line['columns'][colname_to_idx['balance']].get('carryover_bounds', False),
                                   line['columns'][colname_to_idx['balance']].get('report_line_id', False)))

        # We are ignoring all grids that have 0 as values, but the belgian government always require a value at
        # least in either the grid 71 or 72. So in the case where both are set to 0, we are adding the grid 71 in the
        # xml with 0 as a value.
        if len([item for item in grids_list if item[0] == '71' or item[0] == '72']) == 0:
            grids_list.append(('71', 0, False, None))

        # Government expects a value also in grid '00' in case of vat_unit
        if options.get('tax_unit') and options.get('tax_unit') != 'company_only' and len([item for item in grids_list if item[0] == '00']) == 0:
            grids_list.append(('00', 0, False, None))

        grids_list = sorted(grids_list, key=lambda a: a[0])
        for code, amount, carryover_bounds, tax_line in grids_list:
            if carryover_bounds:
                amount, dummy = report.get_amounts_after_carryover(tax_line, amount,
                                                                 carryover_bounds, options, 0)
                # Do not add grids that became 0 after carry over
                if amount == 0:
                    continue

            grid_amount_data = {
                'code': code,
                'amount': '%.2f' % amount,
            }
            rslt += Markup("""
            <ns2:Amount GridNumber="%(code)s">%(amount)s</ns2:Amount>""") % grid_amount_data

        rslt += Markup("""
        </ns2:Data>
        <ns2:ClientListingNihil>%(client_nihil)s</ns2:ClientListingNihil>
        <ns2:Ask Restitution="%(ask_restitution)s"/>
        """) % file_data

        if file_data['comment']:
            rslt += Markup("""
        <ns2:Comment>%(comment)s</ns2:Comment>
            """) % file_data

        rslt += Markup("""
    </ns2:VATDeclaration>
</ns2:VATConsignment>
        """)

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': rslt.encode(),
            'file_type': 'xml',
        }

    def _get_deduction_text(self, options):
        # To Override to include deductions in XML
        deduction_dict = options.get('prorata_deduction', {})
        if not deduction_dict.get('prorata'):
            return ''

        return self.env['ir.qweb']._render('l10n_be_reports.vat_export_prorata', deduction_dict)

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        def _evaluate_check(check_func):
            return all(
                check_func(expression_totals)
                for expression_totals in all_column_groups_expression_totals.values()
            )

        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)
        expr_map = {
            line.code: line.expression_ids.filtered(lambda x: x.label == 'balance')
            for line in report.line_ids
            if line.code
        }

        if _evaluate_check(lambda expr_totals: any(
            [expr_totals[expr_map[grid]]['value'] for grid in ('c44', 'c46L', 'c46T', 'c48s44', 'c48s46L', 'c48s46T')]
        )):
            # remind user to submit EC Sales Report if any ec sales related taxes
            warnings['l10n_be_reports.tax_report_warning_ec_sales_reminder'] = {}

        if _evaluate_check(lambda expr_totals: any(
            self.env.company.currency_id.compare_amounts(expr_totals[expr]['value'], 0) < 0 for expr in expr_map.values()
        )):
            warnings['l10n_be_reports.tax_report_warning_negative_amounts'] = {'alert_type': 'danger'}
