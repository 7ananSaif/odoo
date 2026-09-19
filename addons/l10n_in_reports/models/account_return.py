import base64
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from markupsafe import Markup

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.addons.l10n_in_reports.tools.gstr1_spreadsheet_generator import GSTR1SpreadsheetGenerator
from odoo.exceptions import UserError, AccessError, ValidationError, RedirectWarning
from odoo.fields import Domain
from odoo.tools import date_utils, float_is_zero, html_escape, SQL
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from .irn_exception import IrnException

import logging

_logger = logging.getLogger(__name__)
TOLERANCE_AMOUNT = 1.0  # Default fallback tolerance amount for GSTR-2B matching if the system parameter is unset.


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    states_workflow = fields.Selection(selection_add=[('l10n_in_gstr1_status', 'India GSTR-1'),
                                                      ('l10n_in_gstr2b_status', 'India GSTR-2B')])


class AccountReturn(models.Model):
    _inherit = 'account.return'

    # ===============================
    # GSTR-1
    # ===============================

    l10n_in_doc_summary_line_ids = fields.One2many('l10n_in.gstr.document.summary.line', 'return_period_id')
    l10n_in_gstr_reference = fields.Char(string="GSTR-1 Submit Reference")
    l10n_in_gstr1_status = fields.Selection(selection=[
        ('new', 'New'),
        ('reviewed', 'Review'),
        ('sending', 'Send'),
        ('sending_error', 'Sending Error'),
        ('waiting_for_status', "Waiting for Status"),
        ('sent', 'Submit'),
        ('error_in_invoice', 'Error in Invoice'),
        ('filed', 'Complete')
    ], default="new", readonly=True, tracking=True)
    l10n_in_gstr1_blocking_level = fields.Selection(
        selection=[('warning', 'Warning'), ('error', 'Error')],
        help="Blocks the current operation of the document depending on the error severity:\n"
        "  * Warning: there is an error that doesn't prevent the current Electronic Return filing operation to succeed.\n"
        "  * Error: there is an error that blocks the current Electronic Return filing operation.")
    l10n_in_month_year = fields.Char(compute="_compute_rtn_period_month_year", string="Return Period", store=True)

    # ===============================
    # GSTR-2B
    # ===============================

    l10n_in_gstr2b_status = fields.Selection(selection=[
        ('new', 'New'),
        ('reviewed', 'Review'),
        ('fetching', 'Fetching'),
        ('fetch', 'Fetch'),
        ('error_in_fetching', 'Error In Fetching'),
        ('matched', 'Match'),
        ('partially_matched', 'Partially Matched'),
        ('completed', 'Complete')
    ], default="new", string="GSTR-2B Status", readonly=True, tracking=True)
    # if there is big data then it's give in multi-json
    l10n_in_gstr2b_json_ids = fields.Many2many('ir.attachment', 'account_return_gstr2b_json_rel', string='GSTR2B JSON from portal', bypass_search_access=True)
    l10n_in_gstr2b_blocking_level = fields.Selection(
        selection=[('warning', 'Warning'), ('error', 'Error')],
        help="Blocks the current operation of the document depending on the error severity:\n"
        "  * Warning: there is an error that doesn't prevent the current Electronic Return filing operation to succeed.\n"
        "  * Error: there is an error that blocks the current Electronic Return filing operation.")

    # ===============================
    # Bill using IRN
    # ===============================

    l10n_in_irn_status = fields.Selection(selection=[
        ('to_download', 'To Download'),
        ('to_process', 'To Process'),
        ('process_with_error', 'Process With Error')
    ], string="IRN Status", readonly=True, tracking=True)
    l10n_in_irn_json_attachment_ids = fields.Many2many('ir.attachment', 'irn_attachment_portal_account_return_json', string='JSON with list of IRNs', bypass_search_access=True)
    l10n_in_gstr_activate_einvoice_fetch = fields.Selection(related="company_id.l10n_in_gstr_activate_einvoice_fetch")
    l10n_in_fetch_vendor_edi_feature_enabled = fields.Boolean(related='company_id.l10n_in_fetch_vendor_edi_feature')
    l10n_in_irn_fetch_date = fields.Date(string="Last IRN Fetch Datetime")

    @api.depends('next_state')
    def _compute_show_submit_button(self):
        """
        For GSTR-1, 'to_process' state is added before 'submitted'
        to trigger the cron job. Hence, the submit button should
        be visible in 'to_process' state.
        """
        super()._compute_show_submit_button()
        for record in self:
            if record.type_external_id == "l10n_in_reports.in_gstr1_return_type":
                record.show_submit_button = record.next_state == "sending"

    def _compute_visible_states(self):
        """
        Extend base state computation to apply custom visibility and alert styling
        for Indian GST return types (GSTR1 and GSTR2B).

        General Rule:
        - All states up to the current status remain active.
        - Each visible state gets an `alert_type`:
            * success   → completed successfully
            * warning   → currently in progress / partial match
            * danger    → error encountered
            * secondary → inactive / not reached yet

        GSTR1 Specific:
        - Excludes: 'sending_error', 'waiting_for_status', 'error_in_invoice'
        - 'sending':
            - warning if still processing
            - danger if failed
        - 'sent':
            - success if sent
            - danger if invoice error or waiting with blocking
        - All other active states are success.

        GSTR2B Specific:
        - Excludes: 'fetching', 'error_in_fetching', 'partially_matched'
        - 'fetch':
            - warning if fetching
            - danger if failed
        - 'matched':
            - warning if only partially matched
        - All other active states are success.
        """
        super()._compute_visible_states()
        for record in self:
            new_visible_states = []
            if record.type_external_id == 'l10n_in_reports.in_gstr1_return_type':
                for visible_state in record.visible_states:
                    visible_state_name = visible_state.get('name')
                    if visible_state_name not in ['sending_error', 'waiting_for_status', 'error_in_invoice']:
                        if visible_state_name == 'sending' and record.l10n_in_gstr1_status == 'sending':
                            visible_state['alert_type'] = 'warning'
                        elif (
                            visible_state_name == 'sending' and
                            record.l10n_in_gstr1_status == 'sending_error'
                        ) or (
                            visible_state_name == 'sent' and
                            record.l10n_in_gstr1_status == 'error_in_invoice'
                        ) or (
                            visible_state_name == 'sent' and
                            record.l10n_in_gstr1_status == 'waiting_for_status' and
                            record.l10n_in_gstr1_blocking_level
                        ):
                            visible_state['active'] = True
                            visible_state['alert_type'] = 'danger'
                        elif visible_state['active']:
                            visible_state['alert_type'] = 'success'
                        else:
                            visible_state['alert_type'] = 'secondary'
                        new_visible_states.append(visible_state)

            if record.type_external_id == 'l10n_in_reports.in_gstr2b_return_type':
                for visible_state in record.visible_states:
                    visible_state_name = visible_state.get('name')
                    if visible_state_name not in ['fetching', 'error_in_fetching', 'partially_matched']:
                        if (
                            visible_state_name == 'fetch' and
                            record.l10n_in_gstr2b_status == 'fetching'
                        ) or (
                            visible_state_name == 'matched' and
                            record.l10n_in_gstr2b_status == 'partially_matched'
                        ):
                            visible_state['active'] = True
                            visible_state['alert_type'] = 'warning'
                        elif (
                            visible_state_name == 'fetch' and
                            record.l10n_in_gstr2b_status == 'error_in_fetching'
                        ):
                            visible_state['alert_type'] = 'danger'
                        elif visible_state['active']:
                            visible_state['alert_type'] = 'success'
                        else:
                            visible_state['alert_type'] = 'secondary'
                        new_visible_states.append(visible_state)

            if new_visible_states:
                record.visible_states = new_visible_states

    # ===============================
    # GSTR Common Methods
    # ===============================

    @api.depends("date_to")
    def _compute_rtn_period_month_year(self):
        for period in self:
            if period.date_to:
                period.l10n_in_month_year = period.date_to.strftime("%m%Y")
            else:
                period.l10n_in_month_year = False

    @api.model
    def _l10n_in_check_config(self, company=False):
        company = company or self.company_id
        action = False
        button_name = msg = ""
        if not company.partner_id.check_vat_in(company.vat):
            action = {
                'view_mode': 'form',
                'res_model': 'res.company',
                'type': 'ir.actions.act_window',
                'res_id': company.id,
                'views': [[self.env.ref('base.view_company_form').id, 'form']],
            }
            msg = _("Please set a valid GST number on company.")
            button_name = _('Go to Company')
            raise RedirectWarning(msg, action, button_name)
        if not company.sudo().l10n_in_gstr_gst_username:
            msg = _("First setup GST user name and validate using OTP from configuration")
            button_name = _('Go to the configuration panel')
            action = self.env.ref('account.action_account_config').id
        if not company._is_l10n_in_gstr_token_valid():
            context = {
                'default_company_id': company.id,
                'dialog_size': 'medium',
            }
            form = self.env.ref("l10n_in_reports.view_get_otp_gstr_validate_send_otp")
            action = {
                'name': _('OTP Request'),
                'type': 'ir.actions.act_window',
                'res_model': 'l10n_in.gst.otp.validation',
                'views': [[form.id, 'form']],
                'target': 'new',
                'context': context
            }
            msg = _("The NIC portal connection has expired. To re-initiate the connection, you can send an OTP request.")
            button_name = _('Re-Initiate')
        if msg and button_name and action:
            raise RedirectWarning(msg, action, button_name)

    def _cron_refresh_gst_token(self):
        # If Token is already expired than we can't refresh it.
        companies = self.env['res.company'].search([
            ('vat', '!=', False),
            ('partner_id.country_id.code', '=', 'IN'),
            ('l10n_in_gstr_gst_username', '!=', False),
            ('l10n_in_gst_efiling_feature', '=', True),
        ])
        for company in companies:
            # If token is just refresh in last 30 min then no need to refresh it again
            if company._is_l10n_in_gstr_token_valid() and (
                company.l10n_in_gstr_gst_token_validity - fields.Datetime.now()) > timedelta(minutes=30):
                response = self._l10n_in_refresh_gstr_token_request(company)
                if response.get('error'):
                    message = ''.join([
                        f"<p><b>[{error.get('code', '')}]</b> - <b>{error.get('message', '')}</b></p>"
                        for error in response.get("error", {})])
                    _logger.warning(_('%s', message))
                    continue
                company.write({
                    "l10n_in_gstr_gst_token": response.get('txn'),
                    "l10n_in_gstr_gst_token_validity": fields.Datetime.now() + timedelta(hours=6)
                })

    def _get_l10n_in_error_level(self, error_codes):
        warning_codes = {
            "RTN_24",  # File Generation is in progress, please try after sometime.
            "404",  # Resource temporarily unavailable / not found
            "RET2B1017",  # GSTR-2B data for the selected period is not yet available. Please try after sometime.
        }
        return "warning" if warning_codes.intersection(error_codes) else "error"

    # ===============================
    # GSTR-1
    # ===============================

    def _get_tax_details(self, domain):
        """
            return {
                account.move(1): {
                    account.move.line(1):{
                        'base_amount': 100,
                        'gst_tax_rate': 18.00,
                        'igst': 0.00,
                        'cgst': 9.00,
                        'sgst': 9.00,
                        'cess': 3.33,
                    }
                }
            }
        """
        tax_vals_map = {}
        gst_tags = {
            'igst': self.env.ref('l10n_in.tax_tag_igst'),
            'cgst': self.env.ref('l10n_in.tax_tag_cgst'),
            'sgst': self.env.ref('l10n_in.tax_tag_sgst'),
            'cess': self.env.ref('l10n_in.tax_tag_cess'),
        }
        journal_items = self.env['account.move.line'].search(domain)
        tax_details_sql = self.env['account.move.line']._get_query_tax_details_from_domain(domain=domain)
        tax_details = self.env.execute_query_dict(tax_details_sql)
        # Retrieve base lines and tax lines based on tax_details
        base_lines = self.env['account.move.line'].browse([tax['base_line_id'] for tax in tax_details])
        tax_lines = self.env['account.move.line'].browse([tax['tax_line_id'] for tax in tax_details])
        base_lines_map = {line.id: line for line in base_lines}
        tax_lines_map = {line.id: line for line in tax_lines}
        seen_lines = set()
        for tax_vals in tax_details:
            base_line = base_lines_map[tax_vals['base_line_id']]
            tax_line = tax_lines_map[tax_vals['tax_line_id']]
            seen_lines.add(base_line.id)
            seen_lines.add(tax_line.id)
            move_id = base_line.move_id
            tax_vals_map.setdefault(move_id, {}).setdefault(base_line, {
                'base_amount': tax_vals['base_amount'],
                'l10n_in_reverse_charge': False,
                'rate_by_tax_tag': {},
                'gst_tax_rate': 0.00,
                'igst': 0.00,
                'cgst': 0.00,
                'sgst': 0.00,
                'cess': 0.00,
            })
            for tax_type, tag_id in gst_tags.items():
                if tag_id in tax_line.tax_tag_ids:
                    tax_vals_map[move_id][base_line][tax_type] += tax_vals['tax_amount']
                    if tax_type in ['igst', 'cgst', 'sgst']:
                        tax_vals_map[move_id][base_line]['rate_by_tax_tag'][tax_type] = tax_line.tax_line_id.amount
                    if tax_line.tax_line_id.l10n_in_reverse_charge:
                        tax_vals_map[move_id][base_line]['l10n_in_reverse_charge'] = True
            tax_vals_map[move_id][base_line]['gst_tax_rate'] = sum(tax_vals_map[move_id][base_line]['rate_by_tax_tag'].values())
        # IF line have 0% tax or not have tax then we add it manually
        for journal_item in self.env['account.move.line'].browse(list(set(journal_items.ids) - seen_lines)):
            move_id = journal_item.move_id
            tax_vals_map.setdefault(move_id, {}).setdefault(journal_item, {
                'base_amount': journal_item.balance,
                'l10n_in_reverse_charge': False,
                'gst_tax_rate': 0.0,
                'igst': 0.00,
                'cgst': 0.00,
                'sgst': 0.00,
                'cess': 0.00,
            })
        return tax_vals_map

    def _get_l10n_in_hsn_new_schema_apply_date(self):
        # TODO: Remove this fallback once the government finalizes the official HSN schema date.
        fallback_value = date(2025, 5, 1)
        try:
            param_value = self.env['ir.config_parameter'].sudo().get_param('l10n_in_reports.hsn_new_schema_apply_date')
            return datetime.strptime(param_value, DF).date() if param_value else fallback_value
        except (ValueError, TypeError):
            return fallback_value

    def _get_l10n_in_gstr1_hsn_json(self, journal_items, tax_details_by_move):
        # TO OVERRIDE on Point of sale for get details by product
        """
            This method is return hsn json as below
            Here invoice lines are grouped by GST treatment type, product HSN code, product unit code and GST tax rate.
            {'data/hsn_b2b/hsn_b2c': [{
                'num': 1,
                'hsn_sc': '94038900',
                'uqc': 'UNT',
                'rt': 5.0,
                'qty': 10.0,
                'txval': 40000.0,
                'iamt': 0.0,
                'samt': 1000.0,
                'camt': 1000.0,
                'csamt': 0.0
                }]
            }
        """
        uoms = self.env['uom.uom'].browse(journal_items.product_uom_id.ids)
        uoms.fetch(['l10n_in_code'])
        hsn_json = {}
        hsn_new_schema_apply_date = self._get_l10n_in_hsn_new_schema_apply_date()
        if self.date_from < hsn_new_schema_apply_date:
            hsn_json = {'data': {}}
        else:
            hsn_json = {'hsn_b2b': {}, 'hsn_b2c': {}}
        for move_id in journal_items.mapped('move_id'):
            # We sum value of invoice and credit note
            # so we need positive value for invoice and nagative for credit note
            tax_details = tax_details_by_move.get(move_id, {})
            if 'data' in hsn_json:
                hsn_section = 'data'
            elif move_id.l10n_in_gst_treatment in {'regular', 'composition', 'deemed_export', 'uin_holders', 'special_economic_zone'}:
                hsn_section = 'hsn_b2b'
            else:
                hsn_section = 'hsn_b2c'
            for line, line_tax_details in tax_details.items():
                tax_rate = line_tax_details['gst_tax_rate']
                if tax_rate.is_integer():
                    tax_rate = int(tax_rate)
                uqc = uoms.browse(line.product_uom_id.id).l10n_in_code and uoms.browse(line.product_uom_id.id).l10n_in_code.split("-")[0] or "OTH"
                hsn_code = line.l10n_in_hsn_code
                is_service_line = self.env["account.move"]._l10n_in_is_service_hsn(hsn_code)
                if is_service_line:
                    # If product is service then UQC is Not Applicable (NA)
                    uqc = "NA"
                group_key = "%s-%s-%s" % (
                    tax_rate, hsn_code, uqc)
                hsn_json[hsn_section].setdefault(group_key, {
                    "hsn_sc": self.env["account.move"]._l10n_in_extract_digits(hsn_code),
                    "uqc": uqc,
                    "rt": tax_rate,
                    "qty": 0.00, "txval": 0.00, "iamt": 0.00, "samt": 0.00, "camt": 0.00, "csamt": 0.00})
                hsn_data = hsn_json[hsn_section][group_key]
                if not is_service_line:
                    if move_id.move_type in ('in_refund', 'out_refund'):
                        hsn_data['qty'] -= line.quantity
                    else:
                        hsn_data['qty'] += line.quantity
                hsn_data['txval'] += line_tax_details.get('base_amount', 0.00) * -1
                hsn_data['iamt'] += line_tax_details.get('igst', 0.00) * -1
                hsn_data['samt'] += line_tax_details.get('cgst', 0.00) * -1
                hsn_data['camt'] += line_tax_details.get('sgst', 0.00) * -1
                hsn_data['csamt'] += line_tax_details.get('cess', 0.00) * -1
        return hsn_json

    def _is_l10n_in_einvoice_skippable(self, move_id):
        # OVERRIDE
        pass

    def _get_l10n_in_doc_issue_json(self):
        """
        This method returns the doc_issue JSON (Table 13) as below.
        Here, data is grouped by nature of document and serial range.
            {
            'doc_det': [{
                    'doc_num': 1,
                    'docs': [
                        {
                            'num': 1,
                            'from': invoice.name,
                            'to': invoice.name,
                            'totnum': 1,
                            'cancel': 0,
                            'net_issue': 1,
                        }
                    ]
                }]
            }
        """
        doc_map = defaultdict(list)
        for line in self.l10n_in_doc_summary_line_ids:
            doc_map[int(line.nature_of_document)].append(line)
        doc_det = [
            {
                'doc_num': doc_num,
                'docs': [
                    {
                        'num': idx,
                        'from': line.serial_from,
                        'to': line.serial_to,
                        'totnum': line.total_issued,
                        'cancel': line.total_cancelled,
                        'net_issue': line.total_issued - line.total_cancelled,
                    } for idx, line in enumerate(lines, 1)
                ]
            } for doc_num, lines in sorted(doc_map.items())
        ]
        return {'doc_det': doc_det}

    def _get_l10n_in_gstr1_json(self):

        def _process_hsn_data(hsn_data):
            """Helper function to process HSN data with rounding."""
            return [
                {**hsn_dict, 'num': index, **{
                    key: AccountMove._l10n_in_round_value(hsn_dict.get(key, 0))
                    for key in ('txval', 'iamt', 'camt', 'samt', 'csamt', 'qty')
                }}
                for index, hsn_dict in enumerate(hsn_data.values(), start=1)
            ]

        def _get_b2b_json(journal_items):
            """
            This method is return b2b json as below
            Here itms is group by of invoice line per gst tax rate
            [{
                'ctin': '24AACCT6304M1ZB',
                'inv': [{
                    'inum': 'INV/2022/00005',
                    'idt': '01-04-2022',
                    'val': 100.00,
                    'pos': '24',
                    'rchrg': 'N',
                    'inv_typ': 'R',
                    'etin': "34AACCT6304M1ZB",
                    'diff_percent': 0.65,
                    'itms': [{
                        'num': 1,
                        'itm_det': {
                          'rt': 28.0,
                          'txval': 100.0,
                          'iamt': 0.0,
                          'samt': 9.0,
                          'camt': 9.0,
                          'csamt': 6.5
                        }
                    }]
                }]
            }]
            """
            b2b_json = []
            for partner, items in journal_items.grouped(lambda l: l.move_id.commercial_partner_id).items():
                inv_json_list = []
                for move_id in items.mapped('move_id'):
                    if self._is_l10n_in_einvoice_skippable(move_id):
                        continue
                    lines_json = {}
                    is_reverse_charge = False
                    is_lut = False
                    tax_details = tax_details_by_move.get(move_id)
                    for line, line_tax_details in tax_details.items():
                        # Ignore the nil rated, exempt and non gst lines
                        if line.l10n_in_gstr_section in ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']:
                            continue
                        tax_rate = line_tax_details['gst_tax_rate']
                        if line_tax_details['l10n_in_reverse_charge']:
                            is_reverse_charge = True
                        lines_json.setdefault(tax_rate, {
                            "rt": tax_rate, "txval": 0.00, "iamt": 0.00, "samt": 0.00, "camt": 0.00, "csamt": 0.00})
                        if line.l10n_in_gstr_section == 'sale_sez_wop':
                            is_lut = True
                        lines_json[tax_rate]['txval'] += line_tax_details['base_amount'] * -1
                        lines_json[tax_rate]['iamt'] += line_tax_details['igst'] * -1
                        lines_json[tax_rate]['camt'] += line_tax_details['cgst'] * -1
                        lines_json[tax_rate]['samt'] += line_tax_details['sgst'] * -1
                        lines_json[tax_rate]['csamt'] += line_tax_details['cess'] * -1
                    if lines_json:
                        invoice_type = {
                            'deemed_export': 'DE',
                            'special_economic_zone': 'SEWOP' if is_lut else 'SEWP',
                        }.get(move_id.l10n_in_gst_treatment, 'R')
                        inv_json = {
                            "inum": move_id.name,
                            "idt": move_id.invoice_date.strftime("%d-%m-%Y"),
                            "val": AccountMove._l10n_in_round_value(move_id.amount_total_in_currency_signed),
                            "pos": move_id.l10n_in_state_id.l10n_in_tin,
                            "rchrg": is_reverse_charge and "Y" or "N",
                            "inv_typ": invoice_type,
                            # "etin": move_id.l10n_in_reseller_partner_id.vat or "",
                            "itms": [
                                {"num": index, "itm_det": {
                                    'txval': AccountMove._l10n_in_round_value(line_json.pop('txval')),
                                    'iamt': AccountMove._l10n_in_round_value(line_json.pop('iamt')),
                                    'camt': AccountMove._l10n_in_round_value(line_json.pop('camt')),
                                    'samt': AccountMove._l10n_in_round_value(line_json.pop('samt')),
                                    'csamt': AccountMove._l10n_in_round_value(line_json.pop('csamt')), **line_json}}
                                for index, line_json in enumerate(lines_json.values(), start=1)
                            ],
                        }
                        inv_json_list.append(inv_json)
                if inv_json_list:
                    b2b_json.append({'ctin': partner.vat, 'inv': inv_json_list})
            return b2b_json

        def _get_b2cl_json(journal_items):
            """
            This method is return b2cl json as below
            Here itms is group by of invoice line per gst tax rate
            [{
                'pos': '30',
                'inv': [{
                    'inum': 'INV/2022/00005',
                    'idt': '01-04-2022',
                    'val': 100.00,
                    'diff_percent': 0.65,
                    'itms': [{
                        'num': 1,
                        'itm_det': {
                          'rt': 28.0,
                          'txval': 100.0,
                          'iamt': 0.0,
                          'csamt': 6.5
                        }
                    }]
                }]
            }]
            """
            b2cl_json = []
            for state_id, items in journal_items.grouped(lambda l: l.move_id.l10n_in_state_id).items():
                inv_json_list = []
                for move_id in items.mapped('move_id'):
                    lines_json = {}
                    tax_details = tax_details_by_move.get(move_id)
                    for line, line_tax_details in tax_details.items():
                        if line.l10n_in_gstr_section in ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']:
                            continue
                        tax_rate = line_tax_details.get('gst_tax_rate')
                        lines_json.setdefault(tax_rate, {
                            "rt": tax_rate, "txval": 0.00, "iamt": 0.00, "csamt": 0.00})
                        lines_json[tax_rate]['txval'] += line_tax_details['base_amount'] * -1
                        lines_json[tax_rate]['iamt'] += line_tax_details['igst'] * -1
                        lines_json[tax_rate]['csamt'] += line_tax_details['cess'] * -1
                    if lines_json:
                        inv_json = {
                            "inum": move_id.name,
                            "idt": move_id.invoice_date.strftime("%d-%m-%Y"),
                            "val": AccountMove._l10n_in_round_value(move_id.amount_total_in_currency_signed),
                            # "etin": move_id.l10n_in_reseller_partner_id.vat or "",
                            "itms": [
                                {"num": index, "itm_det": {
                                    'txval': AccountMove._l10n_in_round_value(line_json.pop('txval')),
                                    'iamt': AccountMove._l10n_in_round_value(line_json.pop('iamt')),
                                    'csamt': AccountMove._l10n_in_round_value(line_json.pop('csamt')), **line_json}}
                                for index, line_json in enumerate(lines_json.values(), start=1)
                            ],
                        }
                        inv_json_list.append(inv_json)
                b2cl_json.append({'pos': state_id.l10n_in_tin, 'inv': inv_json_list})
            return b2cl_json

        def _get_b2cs_json(journal_items):
            """
            This method is return b2cs json as below
            Here data is group by gst tax rate and place of supply
            [{
              'sply_ty': 'INTRA',
              'pos': '36',
              'typ': 'OE',
              'rt': 5.0,
              'txval': 100,
              'iamt': 0.0,
              'samt': 2.50,
              'camt': 2.50,
              'csamt': 0.0
            }]
            """
            b2cs_json = {}
            for move_id in journal_items.mapped('move_id'):
                # We sum value of invoice and credit note
                # so we need positive value for invoice and nagative for credit note
                tax_details = tax_details_by_move.get(move_id)
                for line, line_tax_details in tax_details.items():
                    if line.l10n_in_gstr_section in ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']:
                        continue
                    tax_rate = line_tax_details.get('gst_tax_rate')
                    group_key = "%s-%s" % (tax_rate, move_id.l10n_in_state_id.l10n_in_tin)
                    b2cs_json.setdefault(group_key, {
                        "sply_ty": move_id.l10n_in_state_id == move_id.company_id.state_id and "INTRA" or "INTER",
                        "pos": move_id.l10n_in_state_id.l10n_in_tin,
                        "typ": "OE",
                        "rt": tax_rate,
                        "txval": 0.00, "iamt": 0.00, "samt": 0.00, "camt": 0.00, "csamt": 0.00})
                    b2cs_json[group_key]['txval'] += line_tax_details['base_amount'] * -1
                    b2cs_json[group_key]['iamt'] += line_tax_details['igst'] * -1
                    b2cs_json[group_key]['camt'] += line_tax_details['cgst'] * -1
                    b2cs_json[group_key]['samt'] += line_tax_details['sgst'] * -1
                    b2cs_json[group_key]['csamt'] += line_tax_details['cess'] * -1
            return [{
                **d,
                "txval": AccountMove._l10n_in_round_value(d['txval']),
                "iamt": AccountMove._l10n_in_round_value(d['iamt']),
                "samt": AccountMove._l10n_in_round_value(d['samt']),
                "camt": AccountMove._l10n_in_round_value(d['camt']),
                "csamt": AccountMove._l10n_in_round_value(d['csamt']),
            } for d in b2cs_json.values()]

        def _get_cdnr_json(journal_items):
            """
            This method is return cdnr json as below
            Here itms is group by of invoice line per gst tax rate
            [{
                'ctin': '24AACCT6304M1ZB',
                'nt': [{
                    'ntty': 'C',
                    'nt_num': 'RINV/2022/00001',
                    'nt_dt': '02-04-2022',
                    'val': 105296.77,
                    'pos': '24',
                    'rchrg': 'N',
                    'inv_typ': 'R',
                    'diff_percent': 0.65,
                    'itms': [{
                        'num': 1,
                        'itm_det': {
                          'rt': 28.0,
                          'txval': 80000.0,
                          'iamt': 0.0,
                          'samt': 11200.0,
                          'camt': 11200.0,
                          'csamt': 0.0
                        }
                    }]
                }]
            }]
            """
            cdnr_json = []
            for partner, items in journal_items.grouped(lambda l: l.move_id.commercial_partner_id).items():
                inv_json_list = []
                for move_id in items.mapped('move_id'):
                    if self._is_l10n_in_einvoice_skippable(move_id):
                        continue
                    lines_json = {}
                    is_reverse_charge = False
                    tax_details = tax_details_by_move[move_id]
                    is_lut = False
                    for line, line_tax_details in tax_details.items():
                        if line.l10n_in_gstr_section in ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']:
                            continue
                        tax_rate = line_tax_details['gst_tax_rate']
                        if line_tax_details['l10n_in_reverse_charge']:
                            is_reverse_charge = True
                        if line.l10n_in_gstr_section == 'sale_cdnr_sez_wop':
                            is_lut = True
                        lines_json.setdefault(tax_rate, {
                            "rt": tax_rate, "txval": 0.00, "iamt": 0.00, "samt": 0.00, "camt": 0.00, "csamt": 0.00})
                        lines_json[tax_rate]['txval'] += line_tax_details['base_amount']
                        lines_json[tax_rate]['iamt'] += line_tax_details['igst']
                        lines_json[tax_rate]['samt'] += line_tax_details['cgst']
                        lines_json[tax_rate]['camt'] += line_tax_details['sgst']
                        lines_json[tax_rate]['csamt'] += line_tax_details['cess']
                    if lines_json:
                        invoice_type = {
                            'deemed_export': 'DE',
                            'special_economic_zone': 'SEWOP' if is_lut else 'SEWP',
                        }.get(move_id.l10n_in_gst_treatment, 'R')
                        is_out_refund = move_id.move_type == "out_refund"
                        sign = is_out_refund and 1 or -1
                        inv_json = {
                            "ntty": is_out_refund and "C" or "D",
                            "nt_num": move_id.name,
                            "nt_dt": move_id.invoice_date.strftime("%d-%m-%Y"),
                            "val": AccountMove._l10n_in_round_value(move_id.amount_total_in_currency_signed * -sign),
                            "pos": move_id.l10n_in_state_id.l10n_in_tin,
                            "rchrg": is_reverse_charge and "Y" or "N",
                            "inv_typ": invoice_type,
                            "itms": [
                                {"num": index, "itm_det": {
                                    **line_json,
                                    "txval": AccountMove._l10n_in_round_value(line_json['txval'] * sign),
                                    "iamt": AccountMove._l10n_in_round_value(line_json['iamt'] * sign),
                                    "samt": AccountMove._l10n_in_round_value(line_json['samt'] * sign),
                                    "camt": AccountMove._l10n_in_round_value(line_json['camt'] * sign),
                                    "csamt": AccountMove._l10n_in_round_value(line_json['csamt'] * sign),
                                }} for index, line_json in enumerate(lines_json.values(), start=1)
                            ],
                        }
                        inv_json_list.append(inv_json)
                if inv_json_list:
                    cdnr_json.append({'ctin': partner.vat, 'nt': inv_json_list})
            return cdnr_json

        def _get_cdnur_json(journal_items):
            """
            This method is return cdnur json as below
            Here itms is group by of invoice line per gst tax rate
            [{
                'ntty': 'C',
                'nt_num': 'RINV/2022/00002',
                'nt_dt': '02-05-2022',
                'val': 212400.0,
                'pos': '30',
                'typ': 'B2CL',
                'diff_percent': 0.65,
                'itms': [{
                    'num': 1,
                    'itm_det': {
                      'rt': 18.0,
                      'txval': 180000.0,
                      'iamt': 32400.0,
                      'csamt': 0.0
                    }
                }]
            }]
            """
            inv_json_list = []
            for move_id in journal_items.mapped('move_id'):
                tax_details = tax_details_by_move.get(move_id)
                lines_json = {}
                is_lut = False
                for line, line_tax_details in tax_details.items():
                    if line.l10n_in_gstr_section in ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']:
                        continue
                    if line.l10n_in_gstr_section == 'sale_cdnur_exp_wop':
                        is_lut = True
                    tax_rate = line_tax_details['gst_tax_rate']
                    lines_json.setdefault(tax_rate, {
                        "rt": tax_rate, "txval": 0.00, "iamt": 0.00, "csamt": 0.00})
                    lines_json[tax_rate]['txval'] += line_tax_details['base_amount']
                    lines_json[tax_rate]['iamt'] += line_tax_details['igst']
                    lines_json[tax_rate]['csamt'] += line_tax_details['cess']
                if lines_json:
                    is_out_refund = move_id.move_type == "out_refund"
                    sign = is_out_refund and 1 or -1
                    invoice_type = 'B2CL'
                    invoice_total = move_id.amount_total_signed * -sign
                    if move_id.l10n_in_gst_treatment == "overseas" and is_lut:
                        invoice_type = 'EXPWOP'
                    elif move_id.l10n_in_gst_treatment == "overseas":
                        invoice_type = 'EXPWP'
                        # If Base amount and Invoice total is same then add tax values in total for Export with payment only
                        if float_is_zero(invoice_total - sum(line['txval'] for line in lines_json.values()), precision_digits=2):
                            invoice_total += sum(line['iamt'] + line['csamt'] for line in lines_json.values())
                    inv_json = {
                        "ntty": is_out_refund and "C" or "D",
                        "nt_num": move_id.name,
                        "nt_dt": move_id.invoice_date.strftime("%d-%m-%Y"),
                        "val": AccountMove._l10n_in_round_value(invoice_total),
                        "typ": invoice_type,
                        "itms": [
                            {"num": index, "itm_det": {
                                **line_json,
                                "txval": AccountMove._l10n_in_round_value(line_json['txval'] * sign),
                                "iamt": AccountMove._l10n_in_round_value(line_json['iamt'] * sign),
                                "csamt": AccountMove._l10n_in_round_value(line_json['csamt'] * sign),
                            }} for index, line_json in enumerate(lines_json.values(), start=1)
                        ],
                    }
                    if invoice_type == 'B2CL':
                        inv_json.update({"pos": move_id.l10n_in_state_id.l10n_in_tin})
                    inv_json_list.append(inv_json)
            return inv_json_list

        def _get_exp_json(journal_items):
            """
            This method is return exp json as below
            Here itms is group by of invoice line per gst tax rate
            [{
                'exp_typ': 'WPAY',
                'inv': [{
                    'inum': 'INV/2022/00008',
                    'idt': '01-04-2022',
                    'val': 283200.0,
                    'sbnum': '999704',
                    'sbdt': '02/04/2022',
                    'sbpcode': 'INIXY1',
                    'itms': [
                    {
                        'rt': 18.0,
                        'txval': 240000.0,
                        'iamt': 43200.0,
                        'csamt': 0.0
                    }]
                }]
            }]
            """
            export_json = {}
            for move_id in journal_items.mapped('move_id'):
                if self._is_l10n_in_einvoice_skippable(move_id):
                    continue
                tax_details = tax_details_by_move.get(move_id)
                lines_json = {}
                is_lut = False
                for line, line_tax_details in tax_details.items():
                    if line.l10n_in_gstr_section == 'sale_exp_wop':
                        is_lut = True
                    elif line.l10n_in_gstr_section not in ['sale_exp_wp', 'sale_exp_wop']:
                        continue
                    tax_rate = line_tax_details['gst_tax_rate']
                    lines_json.setdefault(tax_rate, {"rt": tax_rate, "txval": 0.00, "iamt": 0.00, "csamt": 0.00})
                    lines_json[tax_rate]['txval'] += line_tax_details['base_amount'] * -1
                    lines_json[tax_rate]['iamt'] += line_tax_details['igst'] * -1
                    lines_json[tax_rate]['csamt'] += line_tax_details['cess'] * -1
                if lines_json:
                    invoice_total = move_id.amount_total_signed
                    invoice_type = 'WOPAY'
                    if not is_lut:
                        invoice_type = 'WPAY'
                        # If Base amount and Invoice total is same then add tax values in total for Export with payment only
                        if float_is_zero(invoice_total - sum(line['txval'] for line in lines_json.values()), precision_digits=2):
                            invoice_total += sum(line['iamt'] + line['csamt'] for line in lines_json.values())
                    export_json.setdefault(invoice_type, [])
                    export_inv = {
                        "inum": move_id.name,
                        "idt": move_id.invoice_date.strftime("%d-%m-%Y"),
                        "val": AccountMove._l10n_in_round_value(invoice_total),
                        "itms": [{
                            **d,
                            "txval": AccountMove._l10n_in_round_value(d['txval']),
                            "iamt": AccountMove._l10n_in_round_value(d['iamt']),
                            "csamt": AccountMove._l10n_in_round_value(d['csamt']),
                            }
                            for d in lines_json.values()],
                    }
                    if move_id.l10n_in_shipping_bill_number:
                        export_inv.update({"sbnum": move_id.l10n_in_shipping_bill_number})
                    if move_id.l10n_in_shipping_bill_date:
                        export_inv.update({"sbdt": move_id.l10n_in_shipping_bill_date.strftime("%d-%m-%Y")})
                    if move_id.l10n_in_shipping_port_code_id.code:
                        export_inv.update({"sbpcode": move_id.l10n_in_shipping_port_code_id.code})
                    export_json[invoice_type].append(export_inv)
            return [{"exp_typ": invoice_type, "inv": inv_json} for invoice_type, inv_json in export_json.items()]

        def _get_nil_json(journal_items):
            """
            This method is return nil json as below
            Here data is grouped by supply_type and sum of base amount of diffrent type of 0% tax
            {
                'inv':[{
                    'sply_ty': 'INTRB2B',
                    'nil_amt': 100.0,
                    'expt_amt': 200.0,
                    'ngsup_amt': 300.0,
                }]
            }
            """
            nil_json = {}
            for move_id in journal_items.mapped('move_id'):
                if self._is_l10n_in_einvoice_skippable(move_id):
                    continue
                # We sum value of invoice and credit note
                # so we need positive value for invoice and nagative for credit note
                tax_details = tax_details_by_move.get(move_id, {})
                same_state = move_id.l10n_in_state_id == move_id.company_id.state_id
                supply_type = ""
                if same_state:
                    if move_id.l10n_in_gst_treatment in ('special_economic_zone', 'deemed_export', 'regular'):
                        supply_type = "INTRAB2B"
                    else:
                        supply_type = "INTRAB2C"
                else:
                    if move_id.l10n_in_gst_treatment in ('special_economic_zone', 'deemed_export', 'regular'):
                        supply_type = "INTRB2B"
                    else:
                        supply_type = "INTRB2C"
                nil_json.setdefault(supply_type, {
                    "sply_ty": supply_type,
                    "nil_amt": 0.00,
                    "expt_amt": 0.00,
                    "ngsup_amt": 0.00,
                })
                for line, line_tax_detail in tax_details.items():
                    base_line_tax_ids = line.tax_ids
                    for tax in base_line_tax_ids:
                        tax_type = tax.l10n_in_tax_type
                        if tax_type == 'nil_rated':
                            nil_json[supply_type]['nil_amt'] += line_tax_detail['base_amount'] * -1
                        if tax_type == 'exempt':
                            nil_json[supply_type]['expt_amt'] += line_tax_detail['base_amount'] * -1
                        if tax_type == 'non_gst':
                            nil_json[supply_type]['ngsup_amt'] += line_tax_detail['base_amount'] * -1
            return nil_json and {'inv': [{
                **d,
                "nil_amt": AccountMove._l10n_in_round_value(d['nil_amt']),
                "expt_amt": AccountMove._l10n_in_round_value(d['expt_amt']),
                "ngsup_amt": AccountMove._l10n_in_round_value(d['ngsup_amt']),
            } for d in nil_json.values()]} or {}

        def _get_supeco_clttx_json(journal_items):
            """
            contains supeco details for section 52
            This method is return clttx list as below
            Here data is grouped by etin(reseller_partner_gstin) and sum of base and gst taxes (TCS 1%)
            [{
                    "etin": "20ALYPD6528PQC5",
                    "suppval": 10000,
                    "igst": 1000,
                    "cgst": 0,
                    "sgst": 0,
                    "cess": 0,
            }]
            """
            clttx_json = {}
            for move_id in journal_items.mapped('move_id'):
                tax_details = tax_details_by_move.get(move_id)
                eco_gstin = move_id.l10n_in_reseller_partner_id.vat
                for line_tax in tax_details.values():
                    clttx_json.setdefault(eco_gstin, {
                        "etin": eco_gstin,
                        "suppval": 0.00,
                        "igst": 0.00,
                        "sgst": 0.00,
                        "cgst": 0.00,
                        "cess": 0.00,
                    })
                    clttx_json[eco_gstin]['suppval'] += line_tax['base_amount'] * -1
                    clttx_json[eco_gstin]['cgst'] += line_tax['cgst'] * -1
                    clttx_json[eco_gstin]['sgst'] += line_tax['sgst'] * -1
                    clttx_json[eco_gstin]['igst'] += line_tax['igst'] * -1
                    clttx_json[eco_gstin]['cess'] += line_tax['cess'] * -1
            return [{
                **d,
                "suppval": AccountMove._l10n_in_round_value(d['suppval']),
                "igst": AccountMove._l10n_in_round_value(d['igst']),
                "cgst": AccountMove._l10n_in_round_value(d['cgst']),
                "sgst": AccountMove._l10n_in_round_value(d['sgst']),
                "cess": AccountMove._l10n_in_round_value(d['cess']),
            } for d in clttx_json.values()]

        def _get_supeco_paytx_json(journal_items):
            """
            contains supeco details for section 9(5)
            This method is return paytx list as below
            Here data is grouped by etin(reseller_partner_gstin)
            [{
                "etin": "20ALYPD6528PQC5",
                "suppval": 10000,
                "igst": 1000,
                "cgst": 0,
                "sgst": 0,
                "cess": 0,
            }]
            """
            paytx_json = {}
            for move_id in journal_items.mapped('move_id'):
                tax_details = tax_details_by_move.get(move_id)
                eco_gstin = move_id.l10n_in_reseller_partner_id.vat
                for line_tax_details in tax_details.values():
                    paytx_json.setdefault(eco_gstin, {
                        "etin": eco_gstin,
                        "suppval": 0.00,
                        "igst": 0.00,
                        "sgst": 0.00,
                        "cgst": 0.00,
                        "cess": 0.00,
                    })
                    paytx_json[eco_gstin]['suppval'] += line_tax_details['base_amount'] * -1
                    paytx_json[eco_gstin]['igst'] += line_tax_details['igst'] * -1
                    paytx_json[eco_gstin]['cgst'] += line_tax_details['cgst'] * -1
                    paytx_json[eco_gstin]['sgst'] += line_tax_details['sgst'] * -1
                    paytx_json[eco_gstin]['cess'] += line_tax_details['cess'] * -1

            return [{
                **d,
                "suppval": AccountMove._l10n_in_round_value(d['suppval']),
                "igst": AccountMove._l10n_in_round_value(d['igst']),
                "cgst": AccountMove._l10n_in_round_value(d['cgst']),
                "sgst": AccountMove._l10n_in_round_value(d['sgst']),
                "cess": AccountMove._l10n_in_round_value(d['cess']),
            } for d in paytx_json.values()]

        AccountMoveLine = self.env['account.move.line'].sudo()
        AccountMove = self.env["account.move"].sudo()
        tax_details_by_move = self._get_tax_details(self._get_section_domain('hsn'))
        hsn_json = self._get_l10n_in_gstr1_hsn_json(AccountMoveLine.search(self._get_section_domain('hsn')), tax_details_by_move)
        nil_json = _get_nil_json(AccountMoveLine.search(self._get_section_domain('nil')))
        return_json = {
            'gstin': self.tax_unit_id.vat or self.company_id.vat,
            'fp': self.l10n_in_month_year,
            'b2b': _get_b2b_json(AccountMoveLine.search(self._get_section_domain('b2b'))),
            'b2cl': _get_b2cl_json(AccountMoveLine.search(self._get_section_domain('b2cl'))),
            'b2cs': _get_b2cs_json(AccountMoveLine.search(self._get_section_domain('b2cs'))),
            'cdnr': _get_cdnr_json(AccountMoveLine.search(self._get_section_domain('cdnr'))),
            'cdnur': _get_cdnur_json(AccountMoveLine.search(self._get_section_domain('cdnur'))),
            'exp': _get_exp_json(AccountMoveLine.search(self._get_section_domain('exp'))),
            'doc_issue': self._get_l10n_in_doc_issue_json(),
        }
        if nil_json:
            return_json.update({'nil': nil_json})
        if hsn_json:
            return_json['hsn'] = {
                hsn_section: _process_hsn_data(hsn_json[hsn_section])
                for hsn_section in hsn_json
            }
        return return_json

    def action_l10n_in_send_gstr1(self):
        """ checks the validations and trigger the cron to send the GSTR-1 data
        """
        cron = self.env.ref('l10n_in_reports.ir_cron_to_send_gstr1_data')
        cron_sudo = cron.sudo()
        if not cron_sudo.active:
            if self.env.user.has_group('base.group_system'):
                message = _("Can not send GSTR-1 data because the required scheduled action '%s' is not active.", cron_sudo.cron_name)
                action = {
                    'name': _("Scheduled Action"),
                    'type': 'ir.actions.act_window',
                    'res_model': 'ir.cron',
                    'res_id': cron.id,
                    'views': [[False, 'form']],
                }
                raise RedirectWarning(message, action, _("Go to Scheduled Action"))
            else:
                raise ValidationError(_("Can not send GSTR-1 data because the required scheduled action '%s' is not active.\nPlease contact your system administrator.", cron_sudo.cron_name))

        self._l10n_in_check_config()
        if not self.env['account.move.line'].sudo().search_count(self._get_section_domain('hsn'), limit=1):
            raise ValidationError(_("There are no transactions available for the current period to send for GSTR-1 filing."))
        self.sudo().write({
            "l10n_in_gstr1_blocking_level": False,
            "state": "sending",
        })
        cron._trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Action triggered — now waiting in queue to prepare and send data."),
                'sticky': True,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _cron_send_gstr1_data(self, job_count=None):
        gstr1_sending = self.search([
            ("l10n_in_gstr1_status", "=", "sending"),
            ("l10n_in_gstr1_blocking_level", "!=", "error"),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
        ])
        process_gstr1 = gstr1_sending[:job_count] if job_count else gstr1_sending
        for return_period in process_gstr1:
            return_period._l10n_in_send_gstr1()
            if len(process_gstr1) > 1:
                self.env.cr.commit()
        if process_gstr1:
            self.env.ref("l10n_in_reports.ir_cron_to_check_gstr1_status")._trigger(fields.Datetime.now() + timedelta(minutes=1))
        if len(process_gstr1) != len(gstr1_sending):
            self.env.ref("l10n_in_reports.ir_cron_to_send_gstr1_data")._trigger()

    def _l10n_in_send_gstr1(self):
        """Send GSTR-1 data to the government portal.
        This method prepares the GSTR-1 JSON payload, attaches it to the return record,
        and sends it to the government portal.
        """
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
                "state": "sending_error",
            })
            msg = _("GSTR-1 submission failed:  GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        error_msg = ""
        json_payload = self._get_l10n_in_gstr1_json()
        self.sudo().message_post(
            subject=_("GSTR-1 Send data"),
            body=_("Attached JSON file contains the submitted GSTR-1 data."),
            attachments=[("status_response.json", json.dumps(json_payload))])

        # Attach the PDF File
        options = self._get_closing_report_options()
        filename = 'gstr1_%s_report.pdf' % self.l10n_in_month_year
        pdf_content = self.type_id.report_id.with_company(self.company_id).export_to_pdf(options)
        pdf_base64 = pdf_content.get("file_content")
        self.sudo().message_post(
            subject=_("PDF file for GSTR-1 return"),
            body=_("PDF file for GSTR-1 return is attached here"),
            attachments=[(filename, pdf_base64)],
        )

        response = self._l10n_in_send_gstr1_request(
            company=self.company_id,
            json_payload=json_payload,
            month_year=self.l10n_in_month_year)

        if response.get("data"):
            self.sudo().write({
                "l10n_in_gstr_reference": response["data"].get("reference_id"),
                "state": "waiting_for_status",
            })
        elif response.get("error"):
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": self._get_l10n_in_error_level(error_codes),
                "state": "sending_error",
            })
        else:
            error_msg = _("Something is wrong in response. Please contact support.\n response: %(response)s", response=response)
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
                "state": "sending_error",
            })

        if self.l10n_in_gstr1_blocking_level:
            self.message_post(body=error_msg)
            act_type_xmlid = 'l10n_in_reports.mail_activity_type_gstr1_errors'
            advisor_user = self._get_gstr_responsible_activity_and_user(act_type_xmlid)
            self.activity_schedule(
                act_type_xmlid=act_type_xmlid,
                user_id=advisor_user.id,
                note=_('Solve GSTR-1 Error')
            )

    def _get_gstr_responsible_activity_and_user(self, act_type_xmlid):
        """
        Retrieve the mail activity type for GSTR-1 exceptions and identify the responsible user.
        """
        act_type = self.env.ref(act_type_xmlid, raise_if_not_found=False)
        if not act_type:
            return

        # Determine the responsible user
        advisor_user = self.env['res.users']
        company_ids = self.company_ids or self.company_id
        if (
            act_type and act_type.default_user_id and
            act_type.default_user_id.has_group(self.env.ref('account.group_account_manager').id) and
            any(company in act_type.default_user_id.company_ids for company in company_ids)
        ):
            advisor_user = act_type.default_user_id
        else:
            field_id = self.env['ir.model.fields']._get('account.return', 'l10n_in_gstr1_status')
            # Search for the last relevant mail message to find a responsible user
            last_message = self.env['mail.message'].search([
                ('model', '=', self._name),
                ('res_id', '=', self.id),
                ('create_uid', '!=', SUPERUSER_ID),
                ('create_uid.all_group_ids', 'in', self.env.ref('account.group_account_manager').ids),
                ('tracking_value_ids.field_id', '=', field_id.id),
            ], limit=1)
            advisor_user = last_message and last_message.create_uid or self.env.user

        return advisor_user

    def check_l10n_in_gstr1_status(self):
        """Check GSTR-1 status and update return record accordingly.
        Following status are handled:
        - P: Processed (success)
        - IP: In Process (waiting)
        - PE: Processed with Error (error in invoice)
        - ER: Error in Response (error in response)
        - Other: Error (unknown status)
        """
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
            })
            msg = _("GSTR-1 check status failed: GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        error_msg = ""
        response = self._l10n_in_get_gstr_status_request(
            company=self.company_id, month_year=self.l10n_in_month_year, reference_id=self.l10n_in_gstr_reference)

        if response.get('data'):
            data = response["data"]
            if data.get("status_cd") == "P":
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": False,
                    "state": "sent",
                    "date_submission": fields.Date.context_today(self)
                })
                odoobot = self.env.ref('base.partner_root')
                self.sudo().message_post(body=_("GSTR-1 Successfully Sent"), author_id=odoobot.id)
            elif data.get("status_cd") == "IP":
                error_msg = _("Waiting for GSTR-1 processing, try in a few minutes")
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": "warning"
                })
            elif data.get("status_cd") in ("PE", "ER"):
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": False,
                    "state": "error_in_invoice"
                })
                message = ""
                act_type_xmlid = 'l10n_in_reports.mail_activity_type_gstr1_exception_to_be_sent'
                AccountMove = self.env['account.move'].with_context(allowed_company_ids=self.company_ids.ids)
                if data.get("status_cd") == "ER":
                    error_report = data.get('error_report', {})
                    message = "[%s] %s" % (error_report.get('error_cd'), error_report.get('error_msg'))
                else:
                    advisor_user = self._get_gstr_responsible_activity_and_user(act_type_xmlid)
                    error_report_summary = {}
                    for section_code, invoices in data.get('error_report', {}).items():
                        error_report_summary[section_code] = {}
                        for invoice in invoices:
                            error_code = invoice.get('error_cd', False)
                            error_message = invoice.get('error_msg', False)
                            invoice_number = None
                            if error_code or error_message:
                                # Extract invoice number based on section_code type
                                if section_code in ('b2b', 'b2cl', 'exp'):
                                    invoice_number = invoice.get('inv')[0].get('inum')
                                if section_code == "cdnr":
                                    invoice_number = invoice.get('nt')[0].get('nt_num')
                                if section_code == 'cdnur':
                                    invoice_number = invoice.get('nt_num')
                            # Search for the corresponding account move
                            move = (
                                AccountMove.search([
                                    ('name', '=', invoice_number),
                                    ('company_id', 'in', self.company_ids.ids or self.company_id.ids)
                                ], limit=1) if invoice_number else AccountMove
                            )
                            # Initialize section_code and move in the error report summary
                            error_report_summary[section_code].setdefault(move, {
                                "move_name": invoice_number,
                                "errors": {}
                            })
                            # Add error details to the corresponding move
                            error_report_summary[section_code][move]["errors"].update({error_code: error_message})
                    # Generate error messages and schedule activities
                    for section_code, moves in error_report_summary.items():
                        message += Markup("<li><b>%s :- </b></li>") % section_code.upper()
                        for move, move_details in moves.items():
                            error_note = Markup().join(Markup("<ul><li>%s - %s</li></ul>") % (error_code, error_message) for error_code, error_message in move_details["errors"].items())
                            if move:
                                # Generate a clickable link for the invoice
                                message += Markup(
                                    "<ul><li>Invoice : <a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a></li>%s</ul>"
                                ) % (move.id, move.name, error_note)
                                move.activity_schedule(
                                    act_type_xmlid=act_type_xmlid,
                                    user_id=advisor_user.id,
                                    note=_('GSTR-1 Processed with Error: %s', error_note)
                                )
                            else:
                                message += error_note
                self.sudo().message_post(
                    subject=_("GSTR-1 Errors"),
                    body=_('%s', message),
                    attachments=[("status_response.json", json.dumps(response))])
            else:
                error_msg = _("Something is wrong in response. Please contact support. \n response: %(response)s", response=response)
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": "error",
                })
        elif response.get("error"):
            error_msg = ""
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": self._get_l10n_in_error_level(error_codes),
            })
        else:
            error_msg = _("Something is wrong in response. Please contact support")
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
            })

        if self.l10n_in_gstr1_blocking_level:
            self.message_post(body=error_msg)

    def _cron_check_gstr1_status(self):
        sent_rtn = self.search([
            ("l10n_in_gstr1_status", "=", "waiting_for_status"),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
        ])
        for rtn in sent_rtn:
            rtn.check_l10n_in_gstr1_status()

    def _get_gst_doc_type_domain(self):
        base_domain = [
            ('name', 'not in', [False, '/', '']),
            ('posted_before', '=', True),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', ['posted', 'cancel']),
        ]
        return {
            '1': base_domain + [('move_type', '=', 'out_invoice'), ('debit_origin_id', "=", False)],
            '4': base_domain + [('move_type', '=', 'out_invoice'), ('debit_origin_id', "!=", False)],
            '5': base_domain + [('move_type', '=', 'out_refund')]
        }

    def _get_section_domain(self, section_code):
        domain = [
            ('company_id', 'in', (self.company_ids or self.company_id).ids),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("move_id.state", "=", "posted"),
            ("display_type", "not in", ('rounding', 'line_note', 'line_section', 'line_subsection'))
        ]
        match section_code:
            case "b2b":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_b2b_rcm', 'sale_b2b_regular', 'sale_deemed_export', 'sale_sez_wp', 'sale_sez_wop'])
                    ]
                )
            case "b2cl":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', '=', 'sale_b2cl')
                    ]
                )
            case "b2cs":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', '=', 'sale_b2cs')
                    ]
                )
            case "cdnr":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_cdnr_rcm', 'sale_cdnr_regular', 'sale_cdnr_deemed_export', 'sale_cdnr_sez_wp', 'sale_cdnr_sez_wop'])
                    ]
                )
            case "cdnur":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_cdnur_b2cl', 'sale_cdnur_exp_wp', 'sale_cdnur_exp_wop'])
                    ]
                )
            case "exp":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_exp_wp', 'sale_exp_wop'])
                    ]
                )
            case "nil":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_nil_rated', 'sale_exempt', 'sale_non_gst_supplies']),
                    ]
                )
            case "hsn":
                return (
                    domain
                    + [
                        ('l10n_in_gstr_section', 'in', ['sale_b2b_rcm', 'sale_b2b_regular', 'sale_b2cl', 'sale_b2cs', 'sale_exp_wp', 'sale_exp_wop', 'sale_sez_wp', 'sale_sez_wop', 'sale_deemed_export', 'sale_cdnr_rcm',
                                                        'sale_cdnr_regular', 'sale_cdnr_deemed_export', 'sale_cdnr_sez_wp', 'sale_cdnr_sez_wop', 'sale_cdnur_b2cl', 'sale_cdnur_exp_wp', 'sale_cdnur_exp_wop', 'sale_nil_rated',
                                                        'sale_exempt', 'sale_non_gst_supplies']),
                    ]
                )

        raise UserError(self.env._("Section %(section)s is unknown", section=section_code))

    def action_generate_document_summary(self):
        self.l10n_in_doc_summary_line_ids.unlink()
        for doc_type, doc_domain in self._get_gst_doc_type_domain().items():
            grouped_data = self.env['account.move'].with_context(
                allowed_company_ids=(self.company_ids or self.company_id).ids
            )._read_group(
                domain=doc_domain,
                groupby=['sequence_prefix', 'state'],
                aggregates=['id:count', 'name:min', 'name:max'],
            )
            summary_map = {}
            for group in grouped_data:
                prefix, state, count, min_name, max_name = group
                summary = summary_map.setdefault(prefix, {
                    'min_name': min_name,
                    'max_name': max_name,
                    'total_issued': 0,
                    'total_cancelled': 0
                })
                summary['min_name'] = min(summary['min_name'], min_name)
                summary['max_name'] = max(summary['max_name'], max_name)
                summary['total_issued'] += count
                if state == 'cancel':
                    summary['total_cancelled'] += count
            self.l10n_in_doc_summary_line_ids.create([
                {
                    'return_period_id': self.id,
                    'nature_of_document': doc_type,
                    'serial_from': values['min_name'],
                    'serial_to': values['max_name'],
                    'total_issued': values['total_issued'],
                    'total_cancelled': values['total_cancelled'],
                }
                for prefix, values in summary_map.items()
            ])
        return self.action_open_document_summary()

    def action_open_document_summary(self):
        context = {'default_return_period_id': self.id}
        if self.l10n_in_gstr1_status == 'filed':
            context.update({
                'create': False, 'edit': False, 'delete': False
            })
        return {
            'name': _("GSTR Document Summary"),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_in.gstr.document.summary.line',
            'views': [(False, 'list')],
            'context': context,
            'domain': [('return_period_id', '=', self.id)],
        }

    def button_gstr1_filed(self):
        if self.l10n_in_gstr1_status != "sent":
            raise UserError(_("Before set as Filed, Status of GSTR-1 must be send"))
        self.write({
            'state': 'filed',
            'is_completed': True
        })

    # ===============================
    # GSTR-2B
    # ===============================

    def action_get_gstr2b_view_reconciled_invoice(self):
        self.ensure_one()
        domain = [("l10n_in_account_return_id", "=", self.id)]
        return {
            "name": _("Reconciled Bill"),
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            'context': {'create': False, "search_default_l10n_in_gstr2b_status": True},
            "domain": domain,
            "view_mode": "list,form",
        }

    def action_get_l10n_in_gstr2b_data(self):
        self._l10n_in_check_config()
        self.sudo().write({
            "state": "fetching",
            "l10n_in_gstr2b_blocking_level": False,
        })
        self.env.ref('l10n_in_reports.ir_cron_auto_sync_gstr2b_data')._trigger()

    def get_l10n_in_gstr2b_data(self):
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": "error",
                "state": "error_in_fetching"
            })
            msg = _("GSTR-2B data fetching failed: GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        response = self._l10n_in_get_gstr2b_data_request(company=self.company_id, month_year=self.l10n_in_month_year)
        if response.get("data"):
            gstr2b_data = response["data"]
            attachment_ids = self.env['ir.attachment'].create({
                'name': 'gstr2b_0.json',
                'mimetype': 'application/json',
                'raw': json.dumps(response),
            })
            if gstr2b_data.get("data", {}).get('fc'):
                number_of_files = gstr2b_data.get("data", {}).get('fc') + 1
                for file_num in range(1, number_of_files):
                    sub_response = self._l10n_in_get_gstr2b_data_request(company=self.company_id, month_year=self.l10n_in_month_year, file_number=file_num)
                    if not sub_response.get('error'):
                        attachment_ids += self.env['ir.attachment'].create({
                            'name': 'gstr2b_%s.json' % (file_num),
                            'mimetype': 'application/json',
                            'raw': json.dumps(sub_response),
                        })
                    else:
                        response = sub_response
            self.sudo().l10n_in_gstr2b_json_ids = attachment_ids
        if response.get('error'):
            error_msg = ""
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": self._get_l10n_in_error_level(error_codes),
                "state": "error_in_fetching"
            })
            self.message_post(body=error_msg)
        else:
            self.write({
                'state': 'fetch'
            })

    def _cron_get_gstr2b_data(self):
        for return_period in self.search([
            ('l10n_in_gstr2b_status', '=', 'fetching'),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
            ('l10n_in_gstr2b_blocking_level', '!=', 'error'),
        ]):
            return_period.get_l10n_in_gstr2b_data()

    def _l10n_in_convert_to_date(self, date):
        # can't use field.date.to_date because formate is different then DEFAULT_SERVER_DATE_FORMAT
        return datetime.strptime(date, "%d-%m-%Y").date()

    def _cron_gstr2b_match_data(self):
        return_periods = self.search([
            ('l10n_in_gstr2b_status', '=', 'fetch'),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
            ('l10n_in_gstr2b_blocking_level', '!=', 'error'),
        ])
        for return_period in return_periods:
            return_period.gstr2b_match_data()

    def gstr2b_match_data(self):
        """
            Matching GSTR-2B data with vendeors bills that bill date is in those return period
            and first match with the reference number and if reference number is match then try
            to match with invoice value, total amount and date of bill,
            if multipls reference found then add exceptions with that bill name,
            if there is no reference number found then metch with invoice value, total amount and date of bill
            and exceptions for reference number.
        """
        def _create_attachment(move, json_data, ref=None):
            return self.env['ir.attachment'].create({
                "name": "gstr2b_matching_data_%s.json" % (ref or move.ref),
                "raw": json.dumps(json_data),
                "res_model": move and "account.move" or False,
                "res_id": move and move.id or False,
                "mimetype": "application/json",
                })

        def _remove_special_characters(ref):
            """Remove special characters from bill reference numbers."""
            if not ref:
                return ref
            pattern = re.compile(r'[^a-zA-Z0-9]')
            return pattern.sub('', ref)

        def _get_tolerance_amount():
            tolerance_value = self.env['ir.config_parameter'].sudo().get_param('l10n_in_reports.gstr2b_matching_tolerance_amount', TOLERANCE_AMOUNT)
            return float(tolerance_value)

        def remove_matched_bill_value(matching_dict, matching_keys_to_remove, matched_bill):
            for key in matching_keys_to_remove:
                # only remove matched bill
                if key in matching_dict:
                    matching_dict[key] -= matched_bill
                    # no value then delete key
                    if not matching_dict[key]:
                        del matching_dict[key]

        def match_bills(gstr2b_streamline_bills, matching_dict):
            create_vals = []
            checked_bills = self.env['account.move']
            try:
                tolerance_amount = _get_tolerance_amount()
            except ValueError:
                tolerance_amount = 0.009
            for gstr2b_bill in gstr2b_streamline_bills:
                bill_type = gstr2b_bill.get('bill_type')
                bill_date = gstr2b_bill.get('bill_date')
                bill_number = gstr2b_bill.get('bill_number')
                bill_vat = gstr2b_bill.get('vat')
                matching_keys = bill_irn = gstr2b_bill.get('irn')
                sanitized_ref = _remove_special_characters(bill_number)
                matched_bills = False
                # check the bill with IRN number first to reduce the unnecessary key generation
                matched_bills = matching_dict.get(bill_irn)
                if not matched_bills:
                    matching_keys = _get_matching_keys(
                        sanitized_ref, bill_vat, bill_date,
                        bill_type, gstr2b_bill.get('bill_total') or gstr2b_bill.get('bill_taxable_value'), bill_irn)
                    for matching_key in matching_keys:
                        if not matched_bills and matching_dict.get(matching_key):
                            matched_bills = matching_dict.get(matching_key)
                            break
                if matched_bills:
                    created_from_reconciliation = matched_bills.filtered(lambda b:
                        b.l10n_in_gstr2b_reconciliation_status == 'gstr2_bills_not_in_odoo' and b.state == 'draft')
                    checked_bills += created_from_reconciliation
                    matched_bills = matched_bills - created_from_reconciliation
                    if len(matched_bills) == 1:
                        remove_matched_bill_value(matching_dict, matching_keys, matched_bills)
                        exception = []
                        is_irn_matched = matched_bills.l10n_in_irn_number == bill_irn
                        if is_irn_matched and matched_bills.state == 'draft':
                            exception.append(_("The IRN number is matching with GSTR-2B, but the bill is not validated yet."))
                        elif matched_bills.ref == bill_number or is_irn_matched:
                            if 'bill_taxable_value' in gstr2b_bill and gstr2b_bill['bill_taxable_value'] != matched_bills.amount_untaxed:
                                exception.append(_("Total Taxable amount as per GSTR-2B is %s", gstr2b_bill['bill_taxable_value']))
                            amount_total = matched_bills.amount_total
                            sign = 1 if matched_bills.is_inbound(include_receipts=True) else -1
                            for line in matched_bills.line_ids:
                                if line.tax_line_id.amount < 0:
                                    amount_total += line.balance * sign
                            if (bill_pos := gstr2b_bill.get('bill_pos')) and bill_pos != matched_bills.l10n_in_state_id.l10n_in_tin:
                                place_of_supply = self.env['res.country.state'].search([('l10n_in_tin', '=', bill_pos)], limit=1)
                                exception.append(_("The place of supply as GSTR-2B is %s", place_of_supply.name))
                            if (
                                'bill_total' in gstr2b_bill
                                and not (amount_total - tolerance_amount <= gstr2b_bill['bill_total'] <= amount_total + tolerance_amount)
                            ):
                                exception.append(_("The total amount as per GSTR-2B is %s", gstr2b_bill['bill_total']))
                            if bill_vat and bill_vat != matched_bills.partner_id.vat:
                                exception.append(_("The GSTIN as per GSTR-2B is %s", bill_vat))
                            if bill_date and bill_date != matched_bills.invoice_date:
                                exception.append(_("The bill date as per GSTR-2B is %s", bill_date))
                            if (
                                matched_bills.move_type == 'in_refund' and bill_type == 'bill'
                                or matched_bills.move_type != 'in_refund' and bill_type == 'credit_note'
                            ):
                                invoice_type = 'Credit Note' if bill_type == 'credit_note' else 'Bill'
                                exception.append(_("The bill type as per GSTR-2B is %s", invoice_type))
                        elif (
                            (gstr2b_bill.get('bill_total') == matched_bills.amount_total
                                or gstr2b_bill.get('bill_taxable_value') == matched_bills.amount_untaxed)
                            and bill_vat == matched_bills.partner_id.vat
                            and bill_date == matched_bills.invoice_date
                            and (matched_bills.move_type == 'in_refund' and bill_type == 'credit_note'
                                or matched_bills.move_type != 'in_refund' and bill_type == 'bill')
                        ):
                            exception.append(_("The reference number as per GSTR-2B is %s", bill_number))
                        if exception and matched_bills.l10n_in_gstr2b_reconciliation_status == "manually_matched":
                            checked_bills += matched_bills
                            continue
                        matched_bills.write({
                            "l10n_in_exception": '<br/>'.join(exception),
                            "l10n_in_gstr2b_reconciliation_status": exception and "partially_matched" or "matched",
                            "l10n_in_account_return_id": self.id,
                        })
                        checked_bills += matched_bills
                        _create_attachment(matched_bills, gstr2b_bill.get('bill_value_json'))
                    else:
                        for bill in matched_bills:
                            _create_attachment(bill, gstr2b_bill.get('bill_value_json'))
                            other_bills = Markup("<br/>").join(Markup("<a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a>") % (
                                    other_bill.id, other_bill.name) for other_bill in matched_bills - bill)
                            bill.message_post(
                                subject=_("GSTR-2B Reconciliation"),
                                body=_(
                                    "The reference number is the same as on other bills: %(other_bills)s",
                                    other_bills=other_bills
                                )
                            )
                        matched_bills.write({
                            "l10n_in_exception": _("We have found the same reference in other bills. For more details, please check the message in Chatter."),
                            'l10n_in_gstr2b_reconciliation_status': "bills_not_in_gstr2",
                            "l10n_in_account_return_id": self.id,
                        })
                        checked_bills += matched_bills
                else:
                    partner = bill_vat and self.env['res.partner'].search([
                        *self.env['res.partner']._check_company_domain(self.company_id),
                        ('vat', '=', bill_vat),
                    ], limit=1)
                    journal = self.env['account.journal'].search([
                        *self.env['account.journal']._check_company_domain(self.company_ids or self.company_id),
                        ('type', '=', 'purchase')
                    ], order="sequence, id", limit=1)
                    if not partner or partner.l10n_in_gst_treatment not in ('deemed_export', 'uin_holders'):
                        l10n_in_gst_treatment = {
                            'impg': 'overseas',
                            'impgsez': 'special_economic_zone',
                        }.get(gstr2b_bill.get('section_code'), 'regular')
                    else:
                        l10n_in_gst_treatment = partner.l10n_in_gst_treatment
                    create_vals.append({
                        "move_type": bill_type == 'credit_note' and "in_refund" or "in_invoice",
                        "ref": bill_number,
                        "invoice_date": bill_date,
                        "partner_id": partner and partner.id or False,
                        "l10n_in_gst_treatment": l10n_in_gst_treatment,
                        "journal_id": journal.id,
                        "l10n_in_gstr2b_reconciliation_status": "gstr2_bills_not_in_odoo",
                        "checked": False,
                        "l10n_in_account_return_id": self.id,
                        "l10n_in_irn_number": bill_irn,
                        "message_ids": [(0, 0, {
                            'model': 'account.move',
                            'body': _(
                                "This bill was created from the GSTR-2B reconciliation because "
                                "no existing bill matched with the given details."
                            ),
                            'attachment_ids': _create_attachment(
                                self.env['account.move'],
                                gstr2b_bill.get('bill_value_json'),
                                ref=bill_number
                            ).ids
                        })]
                    })
            if create_vals:
                created_move = self.env['account.move'].create(create_vals)
                checked_bills += created_move
                self.env.cr.execute(SQL("""
                    UPDATE ir_attachment
                    SET res_id = msg.res_id,
                        res_model = 'account.move'
                    FROM ir_attachment att
                    JOIN message_attachment_rel rel ON rel.attachment_id = att.id
                    JOIN mail_message msg ON msg.id = rel.message_id
                    WHERE att.id = ir_attachment.id
                        AND att.res_model IS NULL
                        AND att.res_id = 0
                        AND msg.model = 'account.move'
                        AND msg.res_id IN %(ids)s
                """, ids=tuple(created_move.ids)))
            return checked_bills

        def _get_matching_keys(ref, vat, invoice_date, invoice_type, amount, irn):
            # remove space from ref
            ref = ref and ref.replace(" ", "")
            key_combinations = [
                (irn,),
                (ref, vat, invoice_type, invoice_date, amount),  # Best case if no irn
                (ref, vat, invoice_type, invoice_date),
                (ref, vat, invoice_type, amount),
                (ref, vat, invoice_type),

                (ref, vat, invoice_date, amount),
                (ref, vat, invoice_date),
                (ref, vat, amount),
                (ref, vat),

                (ref, invoice_type, invoice_date, amount),
                (ref, invoice_type, invoice_date),
                (ref, invoice_type, amount),
                (ref, invoice_type),

                (ref, invoice_date, amount),
                (ref, invoice_date),
                (ref, amount),
                (ref,),
                (vat, invoice_type, invoice_date, amount)  # Worst case
            ]

            # Filter out false keys from key combinations
            filtered_keys = [key for key in key_combinations if any(key)]
            # Convert tuple keys to string keys
            formatted_keys = ["-".join(map(str, key)) for key in filtered_keys]
            return formatted_keys

        def _get_all_bill_by_matching_key(gstr2b_late_streamline_bills):
            AccountMove = self.env["account.move"]
            matching_dict = {}
            domain = ['|',
                ("l10n_in_account_return_id", "=", self.id),
                '&', ("move_type", "in", AccountMove.get_purchase_types()),
                '&', ("invoice_date", ">=", self.date_from),
                '&', ("invoice_date", "<=", self.date_to),
                '&', ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                '|',
                    '&', ("state", "=", "posted"),
                        '&', ("l10n_in_gst_treatment", "not in", ('composition', 'unregistered', 'consumer')),
                            ("line_ids.tax_ids", "!=", False),
                    '&', ("state", "in", ["draft", "cancel"]),
                        ("l10n_in_irn_number", "!=", False),
            ]
            to_match_bills = AccountMove.search(domain)
            for late_bill in gstr2b_late_streamline_bills:
                bill_month_start, bill_month_end = date_utils.get_month(late_bill.get('bill_date'))
                late_bill_domain = [
                    ('l10n_in_account_return_id', '!=', self.id),
                    ("invoice_date", ">=", bill_month_start),
                    ("invoice_date", "<=", bill_month_end),
                    ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                    ("move_type", "in", AccountMove.get_purchase_types()),
                    "|",
                        ("state", "in", ["draft", "cancel"]),
                        '&', '&', '&', ("state", "=", "posted"),
                            ("line_ids.tax_ids", "!=", False),
                            ("l10n_in_gstr2b_reconciliation_status", "not in", ('matched', 'partially_matched', 'manually_matched')),
                            ("l10n_in_gst_treatment", "not in", ('composition', 'unregistered', 'consumer')),
                ]
                if late_bill.get('irn'):
                    late_bill_domain += [
                        "|", ("ref", "=", late_bill.get('bill_number')),
                            ("l10n_in_irn_number", "=", late_bill['irn']),
                    ]
                else:
                    late_bill_domain += [("ref", "=", late_bill.get('bill_number'))]
                to_match_bills += AccountMove.search(late_bill_domain)
            for bill in to_match_bills:
                bill_type = 'bill'
                amount = bill.amount_total
                # For SEZ and overseas amount get from Goverment is amount_untaxed
                if bill.l10n_in_gst_treatment in ('special_economic_zone', 'overseas'):
                    amount = bill.amount_untaxed
                if bill.move_type == 'in_refund':
                    bill_type = 'credit_note'
                # Sanitize the reference to remove any special characters, ensuring it is suitable for matching
                sanitized_ref = _remove_special_characters(bill.ref)
                # Retrieve matching keys based on the sanitized reference, partner VAT, invoice date, bill type, and amount
                matching_keys = _get_matching_keys(sanitized_ref, bill.partner_id.vat, bill.invoice_date, bill_type, amount, bill.l10n_in_irn_number)
                for matching_key in matching_keys:
                    matching_dict.setdefault(matching_key, AccountMove)
                    matching_dict[matching_key] += bill
            return to_match_bills, matching_dict

        def get_streamline_bills_from_json(json_payload):
            vals_list = []
            late_vals_list = []
            gstr2b_bills = json_payload.get("data", {}).get('data', {}).get("docdata", {})
            for section_code, bill_datas in gstr2b_bills.items():
                if section_code in ('b2b', 'cdnr'):
                    for bill_by_vat in bill_datas:
                        key = section_code == 'cdnr' and 'nt' or 'inv'
                        for doc_data in bill_by_vat.get(key):
                            bill_date = self._l10n_in_convert_to_date(doc_data.get('dt'))
                            vals = {
                                'vat': bill_by_vat.get('ctin'),
                                'bill_number': section_code == 'cdnr' and doc_data.get('ntnum') or doc_data.get('inum'),
                                'bill_date': bill_date,
                                'bill_total': doc_data.get('val'),
                                'bill_value_json': doc_data,
                                'bill_type': section_code == 'cdnr' and doc_data.get('typ') == 'C' and 'credit_note' or 'bill',
                                'section_code': section_code,
                                "bill_pos": doc_data.get('pos'),
                                'irn': doc_data.get('irn') and doc_data.get('irn').lower() or False,
                            }
                            vals_list.append(vals)
                            if bill_date < self.date_from:
                                late_vals_list.append(vals)
                if section_code == 'impg':
                    for bill_data in bill_datas:
                        vals_list.append({
                            'vat': False,
                            'bill_number': bill_data.get('boenum'),
                            'bill_date': self._l10n_in_convert_to_date(bill_data.get('boedt')),
                            'bill_taxable_value': bill_data.get('txval'),
                            'bill_value_json': bill_data,
                            'bill_type': 'bill',
                            'section_code': section_code,
                        })
                if section_code == 'impgsez':
                    for bill_by_vat in bill_datas:
                        for bill_data in bill_by_vat.get('boe'):
                            vals_list.append({
                                'vat': bill_by_vat.get('ctin'),
                                'bill_number': bill_data.get('boenum'),
                                'bill_date': self._l10n_in_convert_to_date(bill_data.get('boedt')),
                                'bill_taxable_value': bill_data.get('txval'),
                                'bill_value_json': bill_data,
                                'bill_type': 'bill',
                                'section_code': section_code,
                            })
            return vals_list, late_vals_list

        def process_json(json_dump_list):
            gstr2b_streamline_bills = []
            gstr2b_late_streamline_bills = []
            for json_dump in json_dump_list:
                json_payload = json.loads(json_dump)
                vals_list, late_vals_list = get_streamline_bills_from_json(json_payload)
                gstr2b_streamline_bills += vals_list
                gstr2b_late_streamline_bills += late_vals_list
            to_match_bills, matching_dict = _get_all_bill_by_matching_key(gstr2b_late_streamline_bills)
            checked_invoice = match_bills(gstr2b_streamline_bills, matching_dict)
            self.sudo().state = len(to_match_bills) == len(
                checked_invoice.filtered(lambda l: l.l10n_in_gstr2b_reconciliation_status in ('matched'))
            ) and 'matched' or 'partially_matched'
            invoice_not_in_gstr2b = (to_match_bills - checked_invoice)
            invoice_not_in_gstr2b.write({
                'l10n_in_gstr2b_reconciliation_status': "bills_not_in_gstr2",
                'l10n_in_exception': "Not Available in GSTR2B",
                "l10n_in_account_return_id": self.id,
            })

        json_payload_list = []
        for json_file in self.sudo().l10n_in_gstr2b_json_ids:
            if json_file.mimetype == 'application/json':
                json_payload_list.append(json_file.raw)
        if json_payload_list:
            process_json(json_payload_list)
        else:
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": "error",
                "state": "error_in_fetching",
            })
            msg = _("Somehow, the attached GSTR2B file is not in JSON format.")
            self.message_post(body=msg)

    def button_gstr2b_completed(self):
        if not self.l10n_in_gstr2b_status in ('matched', 'partially_matched'):
            raise UserError(_("Status of GSTR-2B must be fully matched or partially matched"))
        if not self.is_completed:
            self.write({
                'state': 'completed',
                'is_completed': True
            })

    # ===============================
    # Bills from E-Invoice IRN
    # ===============================

    def action_l10n_in_get_irn_data(self):
        """
        Fetch the IRN (Invoice Reference Number) data for the company.
        Ensures the company is in production and has IAP credits, then triggers a cron to fetch
        the list of IRNs relevant to the current GST period.

        :returns: a notification action informing the user that the fetch is in progress.
        """
        if self.company_id.sudo().l10n_in_edi_production_env:
            edi_credits = self.env["iap.account"].get_credits(service_name="l10n_in_edi")
            if edi_credits < 3:
                self.l10n_in_irn_status = 'process_with_error'
                self.message_post(
                    body=self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                )
                return True
        self._l10n_in_check_config()
        self.l10n_in_irn_status = 'to_download'
        self.message_post(body=_("IRN Processing is running in the background."))
        self.env.ref('l10n_in_reports.ir_cron_auto_sync_einvoice_irn')._trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'sticky': False,
                'message': _("Processing is running in the background. You can continue your work."),
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _get_l10n_in_irn_data(self):
        """ Fetch and process IRN data
        The process of retrieving IRN data entails the following steps:
        1. Obtain an e-invoice file token from the IAP.
        2. Use the token to retrieve the e-invoice file details, these include encryption keys and file URLs.
        3. Retrieve the IRN list file data from the encrypted file URLs, creates JSON attachments for each file. In most cases there is only one.
        4. Update the IRN status and trigger the next step in the workflow if successful.
        """
        def extract_token_from_error(response):
            """
            Extracts a file token from a specific error message if the error code matches.
            Handles specific errors and performs appropriate actions.
            :param response: The JSON response containing error details.
            :returns:
                - The extracted token as a string if `EINV30130` is found.
                - A dictionary with `error_code` if `EINV30109` is found (indicates retry).
                - `False` if no relevant error is found.
            """
            errors = response.get('error', [])
            if isinstance(errors, dict):
                errors['code'] = errors.pop('error_cd', None)
            for error in list(errors):
                error_code = error.get('code', '')
                # Handle `EINV30130`: Extract file token from the error message
                if error_code == 'EINV30130':
                    token_match = re.search(r'token\s([a-f0-9]+)(?=.*The link is valid till 1 day)', error.get('message', ''))
                    if token_match:
                        return token_match.group(1)
                # Handle `EINV30109`: File generation in progress, schedule a retry
                elif error_code == 'EINV30109':
                    # Dynamically activate and schedule a retry for the cron job after 10 minutes
                    self.env.ref("l10n_in_reports.ir_cron_auto_sync_einvoice_irn")._trigger(
                        fields.Datetime.now() + timedelta(minutes=10)
                    )
                    self.message_post(body=_("File generation is in progress on the GST portal. Auto retry in 10 minutes."))
                    return 'EINV30109_file_under_process'
            return False

        # Retrieve file token
        file_token_response = self._l10n_in_get_einvoice_file_token_request(
            company=self.company_id,
            month_year=self.l10n_in_month_year,
            section_code="B2B",
        )
        if (file_token := file_token_response.get('data', {}).get('token')) is None:
            file_token = extract_token_from_error(file_token_response)
        if file_token == 'EINV30109_file_under_process':
            return False
        if not file_token:
            raise IrnException(file_token_response.get('error', {}))
        # Retrieve encryption keys and URLs for the e-invoice files
        einvoice_details_response = self._l10n_in_get_einvoice_details_from_file_request(
            company=self.company_id,
            month_year=self.l10n_in_month_year,
            token=file_token,
        )
        if not (
            (data := einvoice_details_response.get('data', {}))
            and (url_list := [url['ul'] for url in data.get('urls') if 'ul' in url])
            and (key := data.get('ek'))
        ):
            raise IrnException(einvoice_details_response.get('error', {}))
        # Process the URLs to fetch IRN data and create attachments, exluding those that already exist
        attachment_ids = self.env['ir.attachment']
        for url in url_list:
            irn_details_response = self._l10n_in_gstr_encrypted_large_file_data_request(
                company=self.company_id,
                month_year=self.l10n_in_month_year,
                url=url,
                encryption_key=key,
            )
            data = irn_details_response.get('data', {})
            if not data or not data.get('irnList', {}):
                raise IrnException(irn_details_response.get('error', {}))
            attachment_ids |= self.env['ir.attachment'].create({
                'name': f'file_{url}.json',
                'mimetype': 'application/json',
                'raw': json.dumps(data),
            })
        if attachment_ids:
            self.l10n_in_irn_json_attachment_ids.unlink()
            self.l10n_in_irn_json_attachment_ids = attachment_ids
        # Update the IRN status and trigger the next workflow step
        self.l10n_in_irn_status = "to_process"
        self.env.ref('l10n_in_reports.ir_cron_auto_match_einvoice_irn')._trigger()

    def l10n_in_irn_match_data(self):
        """
        Matches or creates bills (account moves) based on IRN (Invoice Reference Number) data retrieved from JSON attachments.

        This method processes JSON data containing IRN information and attempts to match each entry with existing bills in the system.
        If a match is found, the IRN number is updated. If no match is found, a new bill is created.
        It handles updates, cancellations, and posting relevant messages based on the IRN status.
        """
        AccountMove = self.env['account.move']
        checked_moves = self.env['account.move']
        # Collect JSON data from the attachments
        json_payload_list = [
            json_file.raw
            for json_file in self.l10n_in_irn_json_attachment_ids
                if json_file.mimetype == 'application/json'
        ]

        if not json_payload_list:
            # No valid JSON attachments found, log an error
            self.l10n_in_irn_status = "process_with_error"
            msg = _("Somehow this IRN attachment is not JSON. Please attempt to retrieve the data from the portal again.")
            self.message_post(body=msg)
            return checked_moves

        # Process the JSON data
        irn_numbers = set()
        streamline_bills = []
        for json_dump in json_payload_list:
            json_payload = json.loads(json_dump)
            for entry in json_payload.get('irnList', {}):
                ctin = entry.get('ctin')
                irn_details = entry.get('irnDtl', [])
                for detail in irn_details:
                    vals = {
                        'vat': ctin,
                        'bill_number': detail.get('docNum'),
                        'bill_date': datetime.strptime(detail.get('docDt'), '%d/%m/%Y').strftime('%Y-%m-%d'),
                        'bill_total': detail.get('totInvAmt'),
                        'bill_value_json': detail,
                        'bill_type': detail.get('docType'),
                        'section_code': detail.get('supplyType'),
                        'irn_number': detail.get('irn'),
                        'l10n_in_irn_status': detail.get('irnStatus'),
                        'ack_no': detail.get('ackNo'),
                        'ack_date': detail.get('ackDt'),
                        'ewb_no': detail.get('ewbNo'),
                        'ewb_date': detail.get('ewbDt'),
                        'cancel_date': detail.get('cnldt')
                    }
                    streamline_bills.append(vals)
                    irn_numbers.add(detail.get('irn'))

        # Perform bulk search for bills with matching IRN numbers
        existing_bills = AccountMove.search([
            ("move_type", "in", AccountMove.get_purchase_types()),
            ("l10n_in_irn_number", "in", list(irn_numbers)),
            ("company_id", "in", self.company_ids.ids or self.company_id.ids),
        ])
        # Create a mapping of existing bills by IRN number
        existing_bills_dict = {bill.l10n_in_irn_number: bill for bill in existing_bills}

        # Match or create bills based on the extracted data
        for bill in streamline_bills:
            irn_number = bill.get('irn_number')
            bill_already_exists = existing_bills_dict.get(irn_number)
            if not bill_already_exists:
                # Check if the bill exists by bill number and date if IRN number does not match
                domain = [
                    ("move_type", "in", AccountMove.get_purchase_types()),
                    ("ref", "=", bill.get('bill_number')),
                    ("invoice_date", "=", bill.get('bill_date')),
                    ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                ]
                if bill.get('vat'):
                    domain.append(("partner_id.vat", "=", bill.get('vat')))
                bill_already_exists = AccountMove.search(domain, limit=1)

                if bill_already_exists:
                    # Update the existing bill with the IRN number
                    bill_already_exists.l10n_in_irn_number = irn_number
                    msg = _("This bill was found in the GST portal while retrieving the list of IRNs.")
                    bill_already_exists.message_post(body=msg)

            if not bill_already_exists:
                # Create a new bill if no match is found
                journal = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(self.company_ids or self.company_id),
                    ('type', '=', 'purchase')
                ], order="sequence, id", limit=1)
                move_type = "in_invoice" if bill.get('bill_type') != "CRN" else "in_refund"
                created_move = self.env['account.move'].with_context(skip_is_manually_modified=True).create({
                    'journal_id': journal.id,
                    'move_type': move_type,
                    'l10n_in_irn_number': irn_number,
                    'invoice_date': bill.get('bill_date'),
                    'ref': bill.get('bill_number')
                })

                if self.l10n_in_gstr_activate_einvoice_fetch == 'automatic':
                    try:
                        gov_json_data = created_move._l10n_in_retrieve_details_from_irn(irn_number, self.company_id)
                    except IrnException as e:
                        if str(e) == 'no-credit':
                            message = self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                        else:
                            message = str(e)
                        created_move.message_post(body=Markup("%s<br/> %s") % (_("Fetching IRN details failed with error(s):"), message))
                        checked_moves |= created_move
                        continue
                    if gov_json_data:
                        # Create an attachment for the fetched data and update the bill
                        attachment = self.env['ir.attachment'].create({
                            # Limit the name to 45 characters to avoid exceeding the limit on e-invoice portal
                            'name': f'{irn_number[:45]}.json',
                            'mimetype': 'application/json',
                            'raw': json.dumps(gov_json_data),
                            'res_model': 'account.move',
                            'res_id': created_move.id,
                        })
                        msg = _("This bill was created from the GST portal because no existing invoice matched the provided details.")
                        created_move.message_post(body=msg)
                        created_move._extend_with_attachments(created_move._to_files_data(attachment), new=True)

                        # Cancel the created bill if the IRN status indicates cancellation
                        if bill.get('l10n_in_irn_status') == 'CNL' and created_move.state != 'cancel':
                            created_move.message_post(body=_("This bill has been marked as canceled based on the e-invoice status."))
                            created_move.button_cancel()
            else:
                # Cancel the existing bill if the IRN status indicates cancellation
                if bill.get('l10n_in_irn_status') == 'CNL' and bill_already_exists.state != 'cancel':
                    bill_already_exists.message_post(
                        body=_("This bill has been marked as canceled based on the e-invoice status.")
                    )
                    bill_already_exists.button_cancel()

            checked_moves |= bill_already_exists or created_move

        # Post a final message with the number of processed bills
        msg = _("Fetching complete. %s bills have been matched or created.", len(checked_moves))
        self.message_post(body=msg)
        self.l10n_in_irn_fetch_date = fields.Date.today()
        self.l10n_in_irn_status = False  # Reset IRN status after processing

    def _cron_get_irn_data(self):
        """
        Cron job to fetch IRN data for GST return periods with 'to_download' status.
        Calls `_get_l10n_in_irn_data()` for each period, handling errors if they occur.

        :rtype: None
        """
        return_periods = self.search([
            ('l10n_in_irn_status', '=', 'to_download'),
            ('company_id.l10n_in_fetch_vendor_edi_feature', '=', True),
        ])
        for return_period in return_periods:
            try:
                return_period._get_l10n_in_irn_data()
            except IrnException as e:
                return_period.l10n_in_irn_status = 'process_with_error'
                if str(e) == 'no-credit':
                    message = self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                else:
                    message = str(e)
                return_period.message_post(body=Markup("%s<br/> %s") % (_("Fetching List of e-invoice..."), message))

    def _cron_irn_match_data(self):
        """
        Cron job method that matches IRN data for GST return periods with 'to_process' status.

        This method searches for all GST return periods marked for IRN data processing and
        calls the `l10n_in_irn_match_data` method on each applicable return period to perform the matching operation.

        :rtype: None
        """
        return_periods = self.search([
            ('l10n_in_irn_status', '=', 'to_process'),
            ('company_id.l10n_in_fetch_vendor_edi_feature', '=', True),
        ])
        for return_period in return_periods:
            return_period.l10n_in_irn_match_data()

    # ========================================
    # Checks and Actions
    # ========================================

    def action_reset_tax_return_common(self):
        """
        If there are any errors in gstr1 sent response then user need to reset the return to 'new' state,
        In order to re-run the checks from after fixing the errors.
        Similary reset the gstr2b to fetch state
        """
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a tax return"))

        if self.type_external_id == 'l10n_in_reports.in_gstr1_return_type':
            self._reset_checks_for_states([self.state, 'new'])
            self.write({
                'state': 'new',
                'l10n_in_gstr1_blocking_level': False,
                'is_completed': False
            })
            self.sudo().message_post(body=_("GSTR-1 return has been reset to new state."))
            return True

        if self.type_external_id == 'l10n_in_reports.in_gstr2b_return_type':
            if self.is_completed:
                self._mark_uncompleted()

            # Reset state bubble to new for the case when state is new but it was marked as complete
            if self.state in ('new', 'error_in_fetching'):
                self._reset_checks_for_states([self.state, 'new'])
                self.write({
                    'state': 'new',
                    'l10n_in_gstr2b_blocking_level': False,
                })
                self.sudo().message_post(body=_("GSTR-2B return has been reset to new state."))
            else:
                self._reset_checks_for_states([self.state, 'fetch'])
                self.write({
                    'state': 'fetch',
                    'l10n_in_gstr2b_blocking_level': False,
                })
                self.sudo().message_post(body=_("GSTR-2B return has been reset to fetch state."))
            return True
        return super().action_reset_tax_return_common()

    def _proceed_with_locking(self, options_to_inject=None):
        """
        Override to handle the final steps of the locking process gstr1 return.
        following steps are performed:
        - run checks in the current stage
        - set the lock date to today
        - change state to 'reviewed' as it's last step in validation process
        """
        self.ensure_one()
        gstr1_return_type = 'l10n_in_reports.in_gstr1_return_type'
        gstr2b_return_type = 'l10n_in_reports.in_gstr2b_return_type'

        domain = [
            ('company_id', '=', self.company_id.id),
            ('type_id', '=', self.type_id.id),
            ('date_deadline', '<', self.date_deadline),
            ('date_lock', '=', False),
            ('is_completed', '=', False),
            ('return_type_category', '!=', 'audit'),
        ]
        count = self.env['account.return'].search_count(domain, limit=1)
        if count:
            raise UserError(_("You cannot lock this return as there are previous returns that are waiting to be posted."))

        if self.type_external_id in (gstr1_return_type, gstr2b_return_type):
            self._check_failing_checks_in_current_stage()
            self.date_lock = fields.Date.context_today(self)
            self.state = 'reviewed'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'title': self.env._("Checks Validated"),
                    'message': self.env._("Checks have been validated successfully. You can now proceed to the next step."),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        return super()._proceed_with_locking(options_to_inject=options_to_inject)

    def _run_checks(self, check_codes_to_ignore):
        if self.type_external_id == 'l10n_in_reports.in_gstr2b_return_type':
            return self._check_suite_in_gstr2b_report(check_codes_to_ignore)
        in_checks = []
        if self.type_external_id == 'l10n_in_reports.in_gstr1_return_type':
            check_codes_to_ignore.update(
                ['check_bills_attachment', 'check_draft_entries', 'check_match_all_bank_entries',
                'check_tax_countries', 'check_company_data'
            ])
            in_checks += self._check_suite_in_gstr1_report(check_codes_to_ignore)
        return super()._run_checks(check_codes_to_ignore) + in_checks

    def _get_l10n_in_reports_aml_domain(self):
        report = self.type_id.report_id
        options = self._get_closing_report_options()
        hsn_base_line_domain = [
                ('l10n_in_gstr_section', '=like', 'sale%'),
                ('display_type', '=', 'product'),
            ]
        options_domain = report._get_options_domain(options, date_scope='strict_range')
        aml_domain = Domain.AND([
                options_domain,
                hsn_base_line_domain,
            ])
        return aml_domain

    def _check_suite_in_gstr1_report(self, check_codes_to_ignore):
        checks = []
        aml_domain = self._get_l10n_in_reports_aml_domain()
        options = self._get_closing_report_options()
        # Invalid Intra-State Tax
        if 'invalid_intra_state_tax' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_intra_state_tax_on_lines(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_intra_state_tax',
                'name': _("Apply Appropriate Tax"),
                'message': _("IGST is not applicable for Intra State Transactions."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid tax for Intra State Transaction"),
                    views=[(False, 'list')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Invalid Inter-State Tax
        if 'invalid_inter_state_tax' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_inter_state_tax_on_lines(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_inter_state_tax',
                'name': _("Wrong CGST/SGST on Inter-State Transactions"),
                'message': _("SGST and CGST are not applicable for Inter State Transactions."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid tax for Inter State Transaction"),
                    views=[(False, 'list')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Missing HSN
        if 'missing_hsn_code' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_no_hsn_products(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'missing_hsn_code',
                'name': _("Missing HSN Codes"),
                'message': _("Certain Product Lines does not have HSN in Journal Items."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Missing HSN for Journal Items"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Invalue UQC code
        if 'invalid_uqc_code' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_uqc_codes(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_uqc_code',
                'name': _("Invalid UQC Codes"),
                'message': _("UQC code must match the Indian GST standards."),
                'records_model': self.env['ir.model']._get('uom.uom').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid UQC Code"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Credit Notes
        if 'fiscal_year_reversed_move' not in check_codes_to_ignore:
            _template, move_ids = self.env['l10n_in.report.handler']._get_out_of_fiscal_year_reversed_moves(options)
            move_count = len(move_ids)
            checks.append({
                'code': 'fiscal_year_reversed_move',
                'name': _("Fiscal Year Reversed Move"),
                'message': _("Some Credit Notes for invoices issued during financial year shouldn't be in GSTR-1 after November 30th,\n"
                    "so it's advisable to remove the tax from it."
                ),
                'records_model': self.env['ir.model']._get('account.move').id,
                'records_count': move_count,
                'result': 'anomaly' if move_ids else 'reviewed',
                'action': move_ids._get_records_action(name=_("Credit Notes")) if move_ids else None,
            })

        if 'unlinked_unregistered_inter_state_reversed_move' not in check_codes_to_ignore:
            _template, move_ids = self.env['l10n_in.report.handler']._get_unlinked_unregistered_inter_state_reversed_moves(options)
            move_count = len(move_ids)
            checks.append({
                'code': 'unlinked_unregistered_inter_state_reversed_move',
                'name': _("Unlinked Unregistered Credit Notes"),
                'message': _("Credit Notes issued without reference to an invoice"),
                'records_model': self.env['ir.model']._get('account.move').id,
                'records_count': move_count,
                'result': 'anomaly' if move_ids else 'reviewed',
                'action': move_ids._get_records_action(name=_("Credit Notes")) if move_ids else None,
            })

        # Document Summary Check
        if 'missing_document_summary' not in check_codes_to_ignore:
            line_ids = self.l10n_in_doc_summary_line_ids.ids
            line_count = len(line_ids)
            checks.append({
                'code': 'missing_document_summary',
                'name': _("Missing Document Summary"),
                'message': _("Document Summary Lines are required for GSTR-1. Click to enter or verify the auto generated document summary lines."),
                'result': 'anomaly' if not line_count else 'reviewed',
                'action': self.action_open_document_summary(),
            })
        return checks

    def _check_suite_in_gstr2b_report(self, check_codes_to_ignore):
        checks = []
        if not self.l10n_in_fetch_vendor_edi_feature_enabled:
            check_codes_to_ignore.add('missing_fetch_einvoice')
            self.check_ids.filtered(lambda check: check.code == 'missing_fetch_einvoice').unlink()
        success_date = self.date_to + relativedelta(months=+1, day=2)
        if 'missing_fetch_einvoice' not in check_codes_to_ignore:
            checks.append({
                'code': 'missing_fetch_einvoice',
                'name': _("Fetch Vendor e-invoice"),
                'message': _("Fetch vendor e-Invoice data for this return period"),
                'result': 'reviewed' if self.l10n_in_irn_fetch_date and self.l10n_in_irn_fetch_date >= success_date else 'anomaly',
            })
        return checks

    def _l10n_in_download_gstr1_xlsx(self, attachment_id):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment_id}?download=true',
            'target': 'self',
        }

    def action_generate_gstr1_xlsx(self):
        """
        Generate GSTR-1 XLSX file from the GSTR-1 JSON data.
        This method retrieves the GSTR-1 JSON data, generates an XLSX file,
        and returns the file for download.
        """
        self.ensure_one()
        gstr1_json = self._get_l10n_in_gstr1_json()

        # Generate XLSX
        xlsx_data = GSTR1SpreadsheetGenerator(gstr1_json).generate()
        filename = 'gstr1_%s_monthly_report.xlsx' % self.l10n_in_month_year

        self.sudo().message_post(
            subject=_("spreadsheet for GSTR-1 return"),
            body=_("Spreadsheet for GSTR-1 return is attached here"),
            attachments=[(filename, xlsx_data)],
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'res_model': 'account.return',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return self._l10n_in_download_gstr1_xlsx(attachment.id)

    def action_submit(self):
        self.ensure_one()
        self._check_failing_checks_in_current_stage()
        if self.type_external_id == 'l10n_in_reports.in_gstr1_return_type':
            return self.env['l10n_in.gstr1.submission.wizard']._open_submission_wizard(self)
        else:
            return super().action_submit()

    def action_check_gstr_status(self):
        self.ensure_one()
        if self.type_external_id != 'l10n_in_reports.in_gstr1_return_type':
            return
        if self.l10n_in_gstr1_status != "waiting_for_status":
            raise AccessError(_("To check status please push the GSTN"))
        self._l10n_in_check_config()
        self.check_l10n_in_gstr1_status()

    def action_gstr2b_fetch(self):
        self.ensure_one()
        if self.type_external_id == 'l10n_in_reports.in_gstr2b_return_type':
            self.is_completed = False
            self.action_get_l10n_in_gstr2b_data()

    # ========================================
    # API calls
    # ========================================

    def _l10n_in_reports_request(self, url, company, params=None):
        if not params:
            params = {}
        params.update({
            "username": company.sudo().l10n_in_gstr_gst_username,
            'gstin': company.vat,
        })
        try:
            return self.env['iap.account']._l10n_in_connect_to_server(
                company.sudo().l10n_in_edi_production_env,
                params,
                url,
                "l10n_in_reports.endpoint"
            )
        except AccessError as e:
            _logger.warning("Connection error: %s", e.args[0])
            return {
                "error": [{
                    "code": "404",
                    "message": _("Unable to connect to the GST service."
                        "The web service may be temporary down. Please try again in a moment.")
                }]
            }

    def _l10n_in_gstr_otp_request(self, company):
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/authentication/otprequest", company=company)

    def _l10n_in_gstr_otp_auth_request(self, company, transaction, otp):
        params = {"auth_token": transaction, "otp": otp}
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/authentication/authtoken", params=params, company=company)

    def _l10n_in_refresh_gstr_token_request(self, company):
        params = {"auth_token": company.sudo().l10n_in_gstr_gst_token}
        return self._l10n_in_reports_request(
            url="/iap/l10n_in_reports/1/authentication/refreshtoken", params=params, company=company)

    def _l10n_in_invalidate_gstr_token_request(self, company):
        params = {"auth_token": company.sudo().l10n_in_gstr_gst_token}
        return self._l10n_in_reports_request("/iap/l10n_in_reports/1/authentication/logout", company, params)

    def _l10n_in_send_gstr1_request(self, company, month_year, json_payload):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "json_payload": json_payload,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/gstr1/retsave", params=params, company=company)

    def _l10n_in_get_gstr_status_request(self, company, month_year, reference_id):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "reference_id": reference_id,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/retstatus", params=params, company=company)

    def _l10n_in_get_gstr2b_data_request(self, company, month_year, file_number=None):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "file_number": file_number,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/gstr2b/all", params=params, company=company)

    def _l10n_in_get_einvoice_file_token_request(self, company, month_year, section_code):
        """
        Retrieve the e-invoice file token for the specified return period and section code.

        :param company: The company for which the e-invoice file token is being retrieved.
        :param month_year: The return period in the format 'MM/YYYY'.
        :param section_code: The section code for the e-invoice.

        :returns: The response from the request containing the e-invoice file token.
        """
        params = {
            "ret_period": month_year,
            "suptyp": section_code,
            "gstin": company.vat,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/einvoice/vendor/irnlist", params=params, company=company)

    def _l10n_in_get_einvoice_details_from_file_request(self, company, month_year, token):
        """
        Get details of the e-invoice file using the provided file token.

        :param company: The company requesting the details.
        :param month_year: Return period ('MM/YYYY').
        :param token: E-invoice file token.

        :returns: E-invoice details response.
        """
        params = {
            "ret_period": month_year,
            "gstin": company.vat,
            "file_token": token,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/einvoice/filedtl", params=params, company=company)

    def _l10n_in_gstr_encrypted_large_file_data_request(self, company, month_year, url, encryption_key):
        """
        Retrieve data from an encrypted large file using its URL and encryption key.
        :returns: Decrypted file data response.
        """
        params = {
            "file_url": url,
            "encryption_key": encryption_key,
            "gstin": company.vat,
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/all/largefile", params=params, company=company)


class AccountReturnCheck(models.Model):
    _inherit = "account.return.check"

    def action_review(self):
        """
        Create the default document summary only on action click
        for missing_document_summary, (if not already created.)
        """
        if self.code == 'missing_document_summary' and not self.return_id.l10n_in_doc_summary_line_ids:
            self.return_id.action_generate_document_summary()
        return super().action_review()

    def action_get_irn_data_from_check(self):
        self.ensure_one()
        if self.code != 'missing_fetch_einvoice':
            return
        self.return_id.action_l10n_in_get_irn_data()
