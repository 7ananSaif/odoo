# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging
import re

from collections import namedtuple
import contextlib
from datetime import datetime
from io import BytesIO

from lxml import etree
from markupsafe import Markup
from psycopg2 import OperationalError


from odoo import fields, models, Command
from odoo.addons.l10n_cl_edi.models.l10n_cl_edi_util import UnexpectedXMLResponse, InvalidToken
from odoo.exceptions import LockError, UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools.translate import _, LazyTranslate
from odoo.tools.float_utils import float_repr

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

XML_NAMESPACES = {
    'ns0': 'http://www.sii.cl/SiiDte',
    'ns1': 'http://www.w3.org/2000/09/xmldsig#',
    'xml_schema': 'http://www.sii.cl/XMLSchema'
}
CURRENCY_CODES = {
    '001': 'ARS',
    '036': 'AUD',
    '004': 'BOB',
    '005': 'BRL',
    '006': 'CAD',
    '999': 'CLP',
    '048': 'CNY',
    '129': 'COP',
    '051': 'DKK',
    '139': 'AED',
    '013': 'USD',
    '127': 'HKD',
    '137': 'INR',
    '135': 'IQD',
    '072': 'JPY',
    '132': 'MXN',
    '096': 'NOK',
    '097': 'NZD',
    '023': 'PYG',
    '024': 'PEN',
    '102': 'GBP',
    '136': 'SGD',
    '128': 'ZAR',
    '113': 'SEK',
    '082': 'CHF',
    '143': 'THB',
    '138': 'TWD',
    '026': 'UYU',
    '134': 'VEF',
    '142': 'EUR',
    '146': 'CZK',
    '166': 'ILS',
    '144': 'KRW',
    '682': 'SAR',
}

try:
    import pdf417gen
except ImportError:
    pdf417gen = None
    _logger.error('Could not import library pdf417gen')


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['l10n_cl.edi.util', 'account.move']

    l10n_cl_sii_barcode = fields.Char(
        string='SII Barcode', readonly=True, copy=False,
        help='This XML contains the portion of the DTE XML that should be coded in PDF417 '
             'and printed in the invoice barcode should be present in the printed invoice report to be valid')
    l10n_cl_dte_status = fields.Selection([
        ('not_sent', 'Pending To Be Sent'),
        ('ask_for_status', 'Ask For Status'),
        ('accepted', 'Accepted'),
        ('objected', 'Accepted With Objections'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('manual', 'Manual'),
    ], string='SII DTE status', copy=False, tracking=True, help="""Status of sending the DTE to the SII:
    - Not sent: the DTE has not been sent to SII but it has created.
    - Ask For Status: The DTE is asking for its status to the SII.
    - Accepted: The DTE has been accepted by SII.
    - Accepted With Objections: The DTE has been accepted with objections by SII.
    - Rejected: The DTE has been rejected by SII.
    - Cancelled: The DTE has been deleted by the user.
    - Manual: The DTE is sent manually, i.e.: the DTE will not be sending manually.""")
    l10n_cl_dte_partner_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
    ], string='Partner DTE status', copy=False, readonly=True, help="""
    Status of sending the DTE to the partner:
    - Not sent: the DTE has not been sent to the partner but it has sent to SII.
    - Sent: The DTE has been sent to the partner.""")
    l10n_cl_dte_acceptation_status = fields.Selection([
        ('received', 'Received'),
        ('ack_sent', 'Acknowledge Sent'),
        ('claimed', 'Claimed'),
        ('accepted', 'Accepted'),
        ('goods', 'Reception 19983'),
        ('accepted_goods', 'Accepted and RG 19983'),
    ], string='DTE Accept status', copy=False, help="""The status of the DTE Acceptation
    Received: the DTE was received by us for vendor bills, by our customers for customer invoices.
    Acknowledge Sent: the Acknowledge has been sent to the vendor.
    Claimed: the DTE was claimed by us for vendor bills, by our customers for customer invoices.
    Accepted: the DTE was accepted by us for vendor bills, by our customers for customer invoices.
    Reception 19983: means that the merchandise or services reception has been created and sent.
    Accepted and RG 19983: means that both the content of the document has been accepted and the merchandise or
services reception has been received as well.
    """)
    l10n_cl_claim = fields.Selection([
        ('ACD', 'Accept the Content of the Document'),
        ('RCD', 'Claim the Content of the Document'),
        ('ERM', 'Provide Receipt of Merchandise or Services'),
        ('RFP', 'Claim for Partial Lack of Merchandise'),
        ('RFT', 'Claim for Total Lack of Merchandise'),
        ('NCA', 'Reception of Cancellation that References Document'),
    ], string='Claim', copy=False, help='The reason why the DTE was accepted or claimed by the customer')
    l10n_cl_claim_description = fields.Char(string='Claim Detail', readonly=True, copy=False)
    l10n_cl_sii_send_file = fields.Many2one('ir.attachment', string='SII Send file', copy=False, groups='base.group_system')
    l10n_cl_dte_file = fields.Many2one('ir.attachment', string='DTE file', copy=False, groups='base.group_system')
    l10n_cl_sii_send_ident = fields.Text(string='SII Send Identification(Track ID)', copy=False, tracking=True)
    l10n_cl_journal_point_of_sale_type = fields.Selection(related='journal_id.l10n_cl_point_of_sale_type')
    l10n_cl_reference_ids = fields.One2many('l10n_cl.edi.reference', 'move_id', string='Reference Records')

    def button_cancel(self):
        for record in self.filtered(lambda x: x.company_id.country_id.code == "CL"):
            # The move cannot be modified once the DTE has been accepted, objected or sent to the SII
            if record.l10n_cl_dte_status in ['accepted', 'objected']:
                l10n_cl_dte_status = dict(record._fields['l10n_cl_dte_status']._description_selection(
                    self.env)).get(record.l10n_cl_dte_status)
                raise UserError(_('This %(document_type)s is in SII status: %(status)s. It cannot be cancelled. '
                                  'Instead you should revert it.',
                                  document_type=record.l10n_latam_document_type_id.name, status=l10n_cl_dte_status))
            elif record.l10n_cl_dte_status == 'ask_for_status':
                raise UserError(_('This %s is in the intermediate state: \'Ask for Status in the SII\'. '
                                  'You will be able to cancel it only when the document has reached the state '
                                  'of rejection. Otherwise, if it were accepted or objected you should revert it '
                                  'with a suitable document instead of cancelling it.') %
                                record.l10n_latam_document_type_id.name)
            record.l10n_cl_dte_status = 'cancelled'
        return super().button_cancel()

    def button_draft(self):
        for record in self.filtered(lambda x: x.company_id.country_id.code == "CL"):
            # The move cannot be modified once the DTE has been accepted, objected or sent to the SII
            if record.l10n_cl_dte_status in ['accepted', 'objected']:
                l10n_cl_dte_status = dict(record._fields['l10n_cl_dte_status']._description_selection(
                    self.env)).get(record.l10n_cl_dte_status)
                raise UserError(_('This %(document_type)s is in SII status %(status)s. It cannot be reset to draft state. '
                                  'Instead you should revert it.',
                    document_type=record.l10n_latam_document_type_id.name, status=l10n_cl_dte_status))
            elif record.l10n_cl_dte_status == 'ask_for_status':
                raise UserError(_('This %s is in the intermediate state: \'Ask for Status in the SII\'. '
                                  'You will be able to reset it to draft only when the document has reached the state '
                                  'of rejection. Otherwise, if it were accepted or objected you should revert it '
                                  'with a suitable document instead of cancelling it.') %
                                record.l10n_latam_document_type_id.name)
            record.l10n_cl_dte_status = None
        return super().button_draft()

    def _post(self, soft=True):
        res = super(AccountMove, self)._post(soft=soft)
        # Avoid to post a vendor bill with a inactive currency created from the incoming mail
        for move in self.filtered(
                lambda x: x.company_id.account_fiscal_country_id.code == "CL" and
                          x.company_id.l10n_cl_dte_service_provider in ['SII', 'SIITEST', 'SIIDEMO'] and
                          x.l10n_latam_use_documents):
            msg_demo = _(' in DEMO mode.') if move.company_id.l10n_cl_dte_service_provider == 'SIIDEMO' else '.'
            for line in move.invoice_line_ids:
                line.name = line.product_id.display_name if not line.name else line.name
            # check if we have the currency active, in order to receive vendor bills correctly.
            if move.move_type in ['in_invoice', 'in_refund'] and not move.currency_id.active:
                raise UserError(
                    _('Invoice %(invoice)s has the currency %(currency)s inactive. Please activate the currency and try again.',
                        invoice=move.name, currency=move.currency_id.name))
            # generation of customer invoices
            if ((move.move_type in ['out_invoice', 'out_refund'] and move.journal_id.type == 'sale')
                    or (move.move_type in ['in_invoice', 'in_refund'] and move.l10n_latam_document_type_id._is_doc_type_vendor())):
                if move.journal_id.l10n_cl_point_of_sale_type != 'online' and not move.l10n_latam_document_type_id._is_doc_type_vendor():
                    move.l10n_cl_dte_status = 'manual'
                    continue
                move._l10n_cl_edi_post_validation()
                move._l10n_cl_create_dte()
                move.l10n_cl_dte_status = 'not_sent'
                dte_signed, file_name = move._l10n_cl_create_dte_envelope()
                attachment = self.env['ir.attachment'].create({
                    'name': 'SII_{}'.format(file_name),
                    'res_id': move.id,
                    'res_model': 'account.move',
                    'datas': base64.b64encode(dte_signed.encode('ISO-8859-1', 'replace')),
                    'type': 'binary',
                })
                move.sudo().l10n_cl_sii_send_file = attachment.id
                move.message_post(
                    body=_('DTE has been created%s', msg_demo),
                    attachment_ids=attachment.ids)
        return res

    def action_reverse(self):
        for record in self.filtered(lambda x: x.company_id.account_fiscal_country_id.code == "CL"):
            if record.l10n_cl_dte_status == 'rejected':
                raise UserError(_('This %s is rejected by SII. Instead of creating a reverse, you should set it to '
                                  'draft state, correct it and post it again.') %
                                record.l10n_latam_document_type_id.name)
        return super().action_reverse()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        reverse_moves = super(AccountMove, self)._reverse_moves(default_values_list, cancel)
        # The reverse move lines of the reverse moves created to correct the original text are replaced by
        # a line with the quantity to 1, the amount to 0 and the original text and correct text as the name
        # since sii regulations stipulate the option to use this kind of document with an amount_untaxed
        # and amount_total equal to $0.0 just in order to inform this is only a text correction.
        # for example, for a bad address or a bad activity description in the originating document.
        if self.env.context.get('default_l10n_cl_edi_reference_doc_code') == '2':
            for move in reverse_moves:
                move.invoice_line_ids = [[5, 0], [0, 0, {
                    'account_id': move.journal_id.default_account_id.id,
                    'name': _('Where it says: %(original_text)s should say: %(corrected_text)s',
                        original_text=self.env.context.get('default_l10n_cl_original_text'),
                        corrected_text=self.env.context.get('default_l10n_cl_corrected_text')),
                    'quantity': 1,
                    'price_unit': 0.0,
                }, ], ]
        return reverse_moves

    def _compute_l10n_latam_document_type(self):
        """
        Extension to ensure the document type for customer invoices is computed based on the partner's taxpayer type and allows
        the SII, the fiscal authority of Chile, to properly validate the record.
        """
        taxpayer_moves = self.filtered(lambda m: m.partner_id.l10n_cl_sii_taxpayer_type in ['1', '3', '4'] and m.move_type == 'out_invoice')
        grouped_doc_types = {doc_type.code: doc_type for doc_type in self.l10n_latam_available_document_type_ids._origin}
        for move in taxpayer_moves:
            taxpayer_type = move.partner_id.l10n_cl_sii_taxpayer_type
            if taxpayer_type == '1':
                if move.debit_origin_id:
                    move.l10n_latam_document_type_id = grouped_doc_types.get('56', False)
                else:
                    move.l10n_latam_document_type_id = grouped_doc_types.get('33', False)
            elif taxpayer_type == '3':
                move.l10n_latam_document_type_id = grouped_doc_types.get('39', False)
            else:
                if move.debit_origin_id:
                    move.l10n_latam_document_type_id = grouped_doc_types.get('111', False)
                else:
                    move.l10n_latam_document_type_id = grouped_doc_types.get('110', False)
        super(AccountMove, self - taxpayer_moves)._compute_l10n_latam_document_type()

    # SII Customer Invoice Buttons

    def l10n_cl_send_dte_to_sii(self, retry_send=True):
        if self.l10n_latam_document_type_id._is_doc_type_ticket():
            return self._l10n_cl_send_dte_to_sii_ticket()
        else:
            return self._l10n_cl_send_dte_to_sii_non_ticket(retry_send=retry_send)

    def _l10n_cl_send_dte_to_sii_ticket(self):
        try:
            self.lock_for_update()
        except LockError:
            if not self.env.context.get('cron_skip_connection_errs'):
                raise UserError(_('This electronic document is being processed already.')) from None
            return
        except OperationalError as e:
            raise UserError(_('An error occurred while processing this document.')) from None
        # To avoid double send on double-click
        if self.l10n_cl_dte_status != "not_sent":
            return None
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        if self.company_id.l10n_cl_dte_service_provider == 'SIIDEMO':
            self.message_post(body=_('This DTE has been generated in DEMO Mode. It is considered as accepted and it won\'t be sent to SII.'))
            self.l10n_cl_dte_status = 'accepted'
            return None
        response = self._send_xml_to_sii_rest(
            self.company_id.l10n_cl_dte_service_provider,
            self.company_id.vat,
            self.sudo().l10n_cl_sii_send_file.name,
            base64.b64decode(self.sudo().l10n_cl_sii_send_file.datas),
            digital_signature_sudo,
        )
        if not response:
            return None

        self.l10n_cl_sii_send_ident = response.get('trackid')
        sii_response_status = response.get('estado')
        self.l10n_cl_dte_status = 'ask_for_status' if sii_response_status == 'REC' else 'rejected'
        self.message_post(body=_('DTE has been sent to SII with response: %s', self._l10n_cl_get_sii_reception_status_message_rest(sii_response_status)))

    def _l10n_cl_send_dte_to_sii_non_ticket(self, retry_send=True):
        """
        Send the DTE to the SII.
        """
        try:
            self.lock_for_update()
        except LockError:
            if not self.env.context.get('cron_skip_connection_errs'):
                raise UserError(_('This invoice is being processed already.')) from None
            return
        # To avoid double send on double-click
        if self.l10n_cl_dte_status != "not_sent":
            return None
        _logger.info('Sending DTE for invoice with ID %s (name: %s)', self.id, self.name)
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        if not digital_signature_sudo.subject_serial_number:
            raise UserError(_("Please set the subject serial number in the certificate: %s", digital_signature_sudo.name))
        if self.company_id.l10n_cl_dte_service_provider == 'SIIDEMO':
            self.message_post(body=_('This DTE has been generated in DEMO Mode. It is considered as accepted and '
                                     'it won\'t be sent to SII.'))
            self.l10n_cl_dte_status = 'accepted'
            return None
        params = {
            'rutSender': digital_signature_sudo.subject_serial_number[:-2],
            'dvSender': digital_signature_sudo.subject_serial_number[-1],
            'rutCompany': self._l10n_cl_format_vat(self.company_id.vat)[:-2],
            'dvCompany': self._l10n_cl_format_vat(self.company_id.vat)[-1],
            'archivo': (
                self.sudo().l10n_cl_sii_send_file.name,
                base64.b64decode(self.sudo().l10n_cl_sii_send_file.datas),
                'application/xml'),
        }
        response = self._send_xml_to_sii(
            self.company_id.l10n_cl_dte_service_provider,
            self.company_id.website,
            params,
            digital_signature_sudo
        )
        if not response:
            return None

        response_parsed = etree.fromstring(response)
        self.l10n_cl_sii_send_ident = response_parsed.findtext('TRACKID')
        sii_response_status = response_parsed.findtext('STATUS')
        if sii_response_status == '5':
            digital_signature_sudo.last_token = False
            _logger.warning('The response status is %s. Clearing the token.',
                          self._l10n_cl_get_sii_reception_status_message(sii_response_status))
            if retry_send:
                _logger.info('Retrying send DTE to SII')
                self.l10n_cl_send_dte_to_sii(retry_send=False)

            # cleans the token and keeps the l10n_cl_dte_status until new attempt to connect
            # would like to resend from here, because we cannot wait till tomorrow to attempt
            # a new send
        else:
            self.l10n_cl_dte_status = 'ask_for_status' if sii_response_status == '0' else 'rejected'
        self.message_post(body=_('DTE has been sent to SII with response: %s.') %
                               self._l10n_cl_get_sii_reception_status_message(sii_response_status))

    def l10n_cl_verify_dte_status(self, send_dte_to_partner=True):
        if self.l10n_latam_document_type_id._is_doc_type_ticket():
            return self._l10n_cl_verify_dte_status_ticket(send_dte_to_partner=send_dte_to_partner)
        else:
            return self._l10n_cl_verify_dte_status_non_ticket(send_dte_to_partner=send_dte_to_partner)

    def _l10n_cl_verify_dte_status_ticket(self, send_dte_to_partner=True):
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        response = self._get_send_status_rest(
            self.company_id.l10n_cl_dte_service_provider,
            self.l10n_cl_sii_send_ident,
            self._l10n_cl_format_vat(self.company_id.vat),
            digital_signature_sudo,
        )
        if not response:
            self.l10n_cl_dte_status = 'ask_for_status'
            return None

        self.l10n_cl_dte_status = self._analyze_sii_result_rest(response)
        message_body = self._l10n_cl_get_verify_status_msg_rest(response)
        if self.l10n_cl_dte_status in ['accepted', 'objected']:
            self.l10n_cl_dte_partner_status = 'not_sent'
            if send_dte_to_partner:
                self._l10n_cl_send_dte_to_partner()
        self.message_post(body=message_body)

    def _l10n_cl_verify_dte_status_non_ticket(self, send_dte_to_partner=True):
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        response = self._get_send_status(
            self.company_id.l10n_cl_dte_service_provider,
            self.l10n_cl_sii_send_ident,
            self._l10n_cl_format_vat(self.company_id.vat),
            digital_signature_sudo)
        if not response:
            self.l10n_cl_dte_status = 'ask_for_status'
            digital_signature_sudo.last_token = False
            return None

        response_parsed = etree.fromstring(response.encode('utf-8'))

        if response_parsed.findtext('{http://www.sii.cl/XMLSchema}RESP_HDR/ESTADO') in ['001', '002', '003']:
            digital_signature_sudo.last_token = False
            _logger.error('Token is invalid.')
            return

        try:
            self.l10n_cl_dte_status = self._analyze_sii_result(response_parsed)
        except UnexpectedXMLResponse:
            # The assumption here is that the unexpected input is intermittent,
            # so we'll retry later. If the same input appears regularly, it should
            # be handled properly in _analyze_sii_result.
            _logger.error("Unexpected XML response:\n%s", response)
            return

        if self.l10n_cl_dte_status in ['accepted', 'objected']:
            self.l10n_cl_dte_partner_status = 'not_sent'
            if send_dte_to_partner:
                self._l10n_cl_send_dte_to_partner()

        self.message_post(
            body=_('Asking for DTE status with response:') +
                 Markup('<br /><li><b>ESTADO</b>: %s</li><li><b>GLOSA</b>: %s</li><li><b>NUM_ATENCION</b>: %s</li>') % (
                     response_parsed.findtext('{http://www.sii.cl/XMLSchema}RESP_HDR/ESTADO'),
                     response_parsed.findtext('{http://www.sii.cl/XMLSchema}RESP_HDR/GLOSA'),
                     response_parsed.findtext('{http://www.sii.cl/XMLSchema}RESP_HDR/NUM_ATENCION')))

    def l10n_cl_verify_claim_status(self):
        if self.company_id.l10n_cl_dte_service_provider in ['SIITEST', 'SIIDEMO']:
            raise UserError(_('This feature is not available in certification/test mode'))
        response = self._get_dte_claim(
            self.company_id.l10n_cl_dte_service_provider,
            self.company_id.vat,
            self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id),
            self.l10n_latam_document_type_id.code,
            self.l10n_latam_document_number
        )
        if not response:
            return None

        try:
            events = response['listaEventosDoc']

            # listaEventosDoc can be either a list or a CompoundValue (which behaves like but isn't a dict)
            if not isinstance(events, list):
                events = [events]

            # listaEventosDoc can also be falsy and empty, for example if codResp is 16 and the client didn't accept or
            # claim the invoice yet. In that case we keep checking until it is and keep the response code unset.
            response_code = False

            # The purpose of this loop is to check each event has a `codEvento` value. If it doesn't something's wrong
            # and we log that as an error. We store the value of the last event in l10n_cl_claim, to mark the claim as
            # successfully parsed. It would make more sense to have it be a list instead of a single value, since a list
            # of events can be returned, but l10n_cl_claim was defined to only hold a single value and that's not
            # something we can change in stable. It's currently not used anywhere in the standard code except to check
            # if we already parsed the claim and if not to retrieve its status from the SII.
            for event in events:
                response_code = event['codEvento']
            self.l10n_cl_claim = response_code
        except Exception as error:
            _logger.error(error)
            if not self.env.context.get('cron_skip_connection_errs'):
                self.message_post(body=_('Asking for claim status with response:') + Markup('<br/>: %s <br/>') % response +
                                       _('failed due to:') + Markup('<br/> %s') % error)
        else:
            self.message_post(body=_('Asking for claim status with response:') + Markup('<br/> %s') % response)

    # SII Vendor Bill Buttons

    def _l10n_cl_send_dte_reception_status(self, status_type):
        """
        Send to the supplier the acceptance or claim of the bill received.
        """
        response_id = self.env['ir.sequence'].browse(self.env.ref('l10n_cl_edi.response_sequence').id).next_by_id()
        StatusType = namedtuple(
            'StatusType',
            ['dte_status', 'dte_glosa_status', 'code_rejected', 'email_template', 'response_type', 'env_type'])
        status_types = {
            'accepted': StatusType(0, 'DTE Aceptado OK', None, 'email_template_receipt_commercial_accept',
                                   'response_dte', 'env_resp'),
            'goods': StatusType(
                1, 'El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) '
                   'del Art. 4, y la letra c) del Art. 5 de la Ley 19.983, acredita que la entrega de '
                   'mercaderias o servicio(s) prestado(s) ha(n) sido recibido(s).',
                    None, 'email_template_receipt_goods', 'receipt_dte', 'recep'),
            'claimed': StatusType(2, 'DTE Rechazado', -1, 'email_template_claimed_ack', 'response_dte', 'env_resp'),
        }
        if not int(self.l10n_latam_document_number):
            raise UserError(_('Please check the document number'))
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        response = self.env['ir.qweb']._render('l10n_cl_edi.%s' % status_types[status_type].response_type, {
            'move': self,
            'doc_id': f'F{int(self.l10n_latam_document_number)}T{self.l10n_latam_document_type_id.code}',
            'format_vat': self._l10n_cl_format_vat,
            'time_stamp': self._get_cl_current_strftime(),
            'response_id': response_id,
            'dte_status': status_types[status_type].dte_status,
            'dte_glosa_status': status_types[status_type].dte_glosa_status,
            'code_rejected': status_types[status_type].code_rejected,
            'signer_rut': digital_signature_sudo.subject_serial_number,
            'rec_address': f'{self.company_id.street}, {self.company_id.street2} {self.company_id.city}',
            '__keep_empty_lines': True,
        })
        signed_response = self._sign_full_xml(
            response, digital_signature_sudo, '', status_types[status_type].env_type,
            self.l10n_latam_document_type_id._is_doc_type_voucher())
        if status_type == 'goods':
            response = self.env['ir.qweb']._render('l10n_cl_edi.envio_receipt_dte', {
                'move': self,
                'format_vat': self._l10n_cl_format_vat,
                'receipt_section': signed_response.replace(Markup('<?xml version="1.0" encoding="ISO-8859-1" ?>'), ''),
                'time_stamp': self._get_cl_current_strftime(),
                '__keep_empty_lines': True,
            })
            signed_response = self._sign_full_xml(
                response, digital_signature_sudo, '', 'env_recep',
                self.l10n_latam_document_type_id._is_doc_type_voucher())
        dte_attachment = self.env['ir.attachment'].create({
            'name': 'DTE_{}_{}.xml'.format(status_type, self.name),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(bytes(signed_response, 'utf-8')),
        })
        self.sudo().l10n_cl_dte_file = dte_attachment.id
        # If we are sending a reception of goods or services we must use an envelope and sign it the same
        # way we do with the invoice (DTE / EnvioDTE) in this case we use the tags: DocumentoRecibo / EnvioRecibos
        email_template = self.env.ref('l10n_cl_edi.%s' % status_types[status_type].email_template)
        email_template.send_mail(self.id, force_send=True, email_values={'attachment_ids': [dte_attachment.id]})

    def l10n_cl_reprocess_acknowledge(self):
        if not self.partner_id:
            raise UserError(_('Please assign a partner before sending the acknowledgement'))
        try:
            self._l10n_cl_send_receipt_acknowledgment()
        except UserError as error:
            self.message_post(body=str(error))

    def _l10n_cl_send_receipt_acknowledgment(self):
        """
        This method sends an xml with the acknowledgement of the reception of the invoice
        by email to the vendor.
        """
        attch_name = 'DTE_{}.xml'.format(self.l10n_latam_document_number)
        dte_attachment = self.sudo().l10n_cl_dte_file
        if not dte_attachment:
            raise UserError(_('DTE attachment not found => %s') % attch_name)
        xml_dte = base64.b64decode(dte_attachment.datas)
        xml_content = etree.fromstring(xml_dte)
        response_id = self.env['ir.sequence'].browse(self.env.ref('l10n_cl_edi.response_sequence').id).next_by_id()
        xml_ack_template = self.env['ir.qweb']._render('l10n_cl_edi.ack_template', {
            'move': self,
            'format_vat': self._l10n_cl_format_vat,
            'get_cl_current_strftime': self._get_cl_current_strftime,
            'response_id': response_id,
            'nmb_envio': 'RESP_%s' % attch_name,
            'envio_dte_id': self._l10n_cl_get_set_dte_id(xml_content),
            'digest_value': xml_content.findtext(
                './/ns1:DigestValue', namespaces={'ns1': 'http://www.w3.org/2000/09/xmldsig#'}),
            '__keep_empty_lines': True,
        })
        xml_ack_template = xml_ack_template.replace(
            '&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace(
            '<?xml version="1.0" encoding="ISO-8859-1" ?>', '')
        try:
            digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        except UserError:
            raise UserError(_('There is no signature available to send acknowledge or acceptation of this DTE. '
                              'Please setup your digital signature'))
        xml_ack = self._sign_full_xml(xml_ack_template, digital_signature_sudo, str(response_id),
                                      'env_resp', self.l10n_latam_document_type_id._is_doc_type_voucher())
        attachment = self.env['ir.attachment'].create({
            'name': 'receipt_acknowledgment_{}.xml'.format(response_id),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(bytes(xml_ack, 'utf-8')),
        })
        self.env.ref('l10n_cl_edi.email_template_receipt_ack').send_mail(self.id, force_send=True, email_values={
            'attachment_ids': attachment.ids})
        self.l10n_cl_dte_acceptation_status = 'ack_sent'

    def _l10n_cl_action_response(self, status_type):
        """
        This method is intended to manage the claim/acceptation/receipt of goods for vendor bill
        """
        accepted_statuses = {'accepted_goods', 'accepted', 'goods'}

        ActionResponse = namedtuple('ActionResponse', ['code', 'category', 'status', 'description'])
        action_response = {
            'accepted': ActionResponse('ACD', _('Claim status'), 'accepted', _('acceptance')),
            'goods': ActionResponse('ERM', _('Reception law 19983'), 'received',
                                _('reception of goods or services RG 19.983')),
            'claimed': ActionResponse('RCD', _('Claim status'), 'claimed', _('claim')),
        }

        if self.company_id.l10n_cl_dte_service_provider == 'SIIDEMO':
            self.message_post(body=_(
                '<strong>WARNING: Simulating %s in Demo Mode</strong>') % action_response[status_type].description)
            self.l10n_cl_dte_acceptation_status = 'accepted_goods' if \
                self.l10n_cl_dte_acceptation_status in accepted_statuses and status_type in accepted_statuses \
                else status_type
            self._l10n_cl_send_dte_reception_status(status_type)
        if not self.l10n_latam_document_type_id._is_doc_type_acceptance():
            raise UserError(_('The document type with code %(code)s cannot be %(status)s',
                            code=self.l10n_latam_document_type_id.code, status=action_response[status_type].status))
        try:
            response = self._send_sii_claim_response(
                self.company_id.l10n_cl_dte_service_provider, self.partner_id.vat,
                self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id), self.l10n_latam_document_type_id.code,
                self.l10n_latam_document_number, action_response[status_type].code)
        except InvalidToken:
            digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
            digital_signature_sudo.last_token = None
            return self._l10n_cl_action_response(status_type)
        if not response:
            return None
        try:
            cod_response = response['codResp']
            description_response = response['descResp']
        except Exception as error:
            _logger.error(error)
            self.message_post(body=_('Exception error parsing the response: %s') % response)
            return None
        if cod_response in [0, 1]:
            # accepted_goods only when both acceptation of the invoice and receipt of goods have been done
            self.l10n_cl_dte_acceptation_status = 'accepted_goods' if \
                self.l10n_cl_dte_acceptation_status in accepted_statuses and status_type in accepted_statuses \
                else status_type
            self._l10n_cl_send_dte_reception_status(status_type)
            msg = _('Document %s was accepted with the following response:') % (
                action_response[status_type].description) + '<br/><strong>%s: %s.</strong>' % (
                cod_response, description_response)
            if self.company_id.l10n_cl_dte_service_provider == 'SIIDEMO':
                msg += _(' -- Response simulated in Demo Mode')
        else:
            msg = _('Document %s failed with the following response:') % (action_response[status_type].description) + \
                  Markup('<br/><strong>%s: %s.</strong>') % (cod_response, description_response)
            if cod_response == 9 and self.company_id.l10n_cl_dte_service_provider == 'SIITEST':
                msg += Markup(_('<br/><br/>If you are trying to test %(status_type)s of documents, you should send this %(document_type)s as a vendor '
                         'to %(company)s before doing the test.')) % {
                        "status_type": action_response[status_type].description,
                        "document_type": self.l10n_latam_document_type_id.name,
                        "company": self.company_id.name,
                    }
        self.message_post(body=msg)

    def l10n_cl_accept_document(self):
        self._l10n_cl_action_response('accepted')

    def l10n_cl_receipt_service_or_merchandise(self):
        self._l10n_cl_action_response('goods')

    def l10n_cl_claim_document(self):
        self._l10n_cl_action_response('claimed')

    # DTE creation
    def _get_last_sequence(self, relaxed=False, with_prefix=None):
        """
        This method extends the base sequence retrieval to handle Chilean electronic documents.
        It checks if there's an available CAF (Código de Autorización de Folios)
        for the current folio number and adjusts the sequence accordingly.
        """
        res = super()._get_last_sequence(relaxed=relaxed, with_prefix=with_prefix)
        if res and self.country_code == "CL" and self.is_sale_document() and self.l10n_latam_document_type_id:
            match = re.search(r'(\d+)$', res)
            if match:
                folio = int(match.group(1))
                available_caf = self.env['l10n_cl.dte.caf'].sudo().search([
                ('final_nb', '>=', folio), ('start_nb', '<=', folio), ('l10n_latam_document_type_id', '=', self.l10n_latam_document_type_id.id),
                ('status', '=', 'in_use'), ('company_id', '=', self.company_id.id)], limit=1)
                if not available_caf:
                    start_nb = self.l10n_latam_document_type_id._get_start_number()
                    res = f"{self.l10n_latam_document_type_id.doc_code_prefix} {start_nb - 1:06d}"
        return res

    def _l10n_cl_create_dte(self):
        folio = int(self.l10n_latam_document_number)
        doc_id_number = 'F{}T{}'.format(folio, self.l10n_latam_document_type_id.code)
        dte_barcode_xml = self._l10n_cl_get_dte_barcode_xml()
        self.l10n_cl_sii_barcode = dte_barcode_xml['barcode']
        dte = self.env['ir.qweb']._render('l10n_cl_edi.dte_template', {
            'move': self,
            'format_vat': self._l10n_cl_format_vat,
            'get_cl_current_strftime': self._get_cl_current_strftime,
            'format_length': self._format_length,
            'format_uom': self._format_uom,
            'float_repr': float_repr,
            'float_rr': self._float_repr_float_round,
            'doc_id': doc_id_number,
            'caf': self.l10n_latam_document_type_id._get_caf_file(self.company_id.id, int(self.l10n_latam_document_number)),
            'amounts': self._l10n_cl_get_amounts(),
            'withholdings': self._l10n_cl_get_withholdings(),
            'dte': dte_barcode_xml['ted'],
            '__keep_empty_lines': True,
        })
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        signed_dte = self._sign_full_xml(
            dte, digital_signature_sudo, doc_id_number, 'doc', self.l10n_latam_document_type_id._is_doc_type_voucher())
        dte_attachment = self.env['ir.attachment'].create({
            'name': 'DTE_{}.xml'.format(self.name),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(signed_dte.encode('ISO-8859-1', 'replace'))
        })
        self.sudo().l10n_cl_dte_file = dte_attachment.id

    def _l10n_cl_create_partner_dte(self):
        dte_signed, file_name = self._l10n_cl_create_dte_envelope(
            '55555555-5' if self.partner_id.l10n_cl_sii_taxpayer_type == '4' else self.partner_id.vat)
        dte_partner_attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(dte_signed.encode('ISO-8859-1', 'replace'))
        })
        self.message_post(
            body=_('Partner DTE has been generated'),
            attachment_ids=[dte_partner_attachment.id])
        return dte_partner_attachment

    def _l10n_cl_create_dte_envelope(self, receiver_rut='60803000-K'):
        file_name = 'F{}T{}.xml'.format(self.l10n_latam_document_number, self.l10n_latam_document_type_id.code)
        digital_signature_sudo = self.company_id.sudo()._get_digital_signature(user_id=self.env.user.id)
        template = self.l10n_latam_document_type_id._is_doc_type_voucher() and self.env.ref(
            'l10n_cl_edi.envio_boleta') or self.env.ref('l10n_cl_edi.envio_dte')
        dte = self.sudo().l10n_cl_dte_file.raw.decode('ISO-8859-1')
        dte = Markup(dte.replace('<?xml version="1.0" encoding="ISO-8859-1" ?>', ''))
        dte_rendered = self.env['ir.qweb']._render(template.id, {
            'move': self,
            'RutEmisor': self._l10n_cl_format_vat(self.company_id.vat),
            'RutEnvia': digital_signature_sudo.subject_serial_number,
            'RutReceptor': receiver_rut,
            'FchResol': self.company_id.l10n_cl_dte_resolution_date,
            'NroResol': self.company_id.l10n_cl_dte_resolution_number,
            'TmstFirmaEnv': self._get_cl_current_strftime(),
            'dte': dte,
            '__keep_empty_lines': True,
        })
        dte_rendered = dte_rendered.replace('<?xml version="1.0" encoding="ISO-8859-1" ?>', '')
        dte_signed = self._sign_full_xml(
            dte_rendered, digital_signature_sudo, 'SetDoc',
            self.l10n_latam_document_type_id._is_doc_type_voucher() and 'bol' or 'env',
            self.l10n_latam_document_type_id._is_doc_type_voucher()
        )
        return dte_signed, file_name

    # DTE sending

    def _l10n_cl_send_dte_to_partner(self):
        # We need a DTE with the partner vat as RutReceptor to be sent to the partner
        dte_partner_attachment = self._l10n_cl_create_partner_dte()
        self.env.ref('l10n_cl_edi.l10n_cl_edi_email_template_invoice').send_mail(
            self.id, force_send=True, email_values={'attachment_ids': [dte_partner_attachment.id]})
        self.l10n_cl_dte_partner_status = 'sent'
        self.message_post(body=_('DTE has been sent to the partner'))

    # Helpers
    def _l10n_cl_edi_currency_validation(self):
        # commented to allow validation to true for every case of invoices (national invoices in foreign currency)
        return True

    def _l10n_cl_edi_post_validation(self):
        if (self.l10n_cl_journal_point_of_sale_type == 'online' and
                not ((self.partner_id.l10n_cl_dte_email or self.commercial_partner_id.l10n_cl_dte_email) and
                     self.company_id.l10n_cl_dte_email) and
                not self.l10n_latam_document_type_id._is_doc_type_export() and
                not self.l10n_latam_document_type_id._is_doc_type_ticket()):
            raise UserError(
                _('The %(partner_type)s %(partner)s has not a DTE email defined. This is mandatory for electronic invoicing.',
                partner_type=_('partner') if not (self.partner_id.l10n_cl_dte_email or
                                      self.commercial_partner_id.l10n_cl_dte_email) else _('company'), partner=self.partner_id.name))
        if datetime.strptime(self._get_cl_current_strftime(), '%Y-%m-%dT%H:%M:%S').date() < self.invoice_date:
            raise UserError(
                _('The stamp date and time cannot be prior to the invoice issue date and time. TIP: check '
                  'in your user preferences if the timezone is "America/Santiago"'))
        if not self.company_id.l10n_cl_dte_service_provider:
            raise UserError(_(
                'You have not selected an invoicing service provider for your company. '
                'Please go to your company and select one'))
        if not self.company_id.l10n_cl_activity_description:
            raise UserError(_(
                'Your company has not an activity description configured. This is mandatory for electronic '
                'invoicing. Please go to your company and set the correct one (www.sii.cl - Mi SII)'))
        if not self.company_id.l10n_cl_company_activity_ids:
            raise UserError(_(
                'There are no activity codes configured in your company. This is mandatory for electronic '
                'invoicing. Please go to your company and set the correct activity codes (www.sii.cl - Mi SII)'))
        if not self.company_id.l10n_cl_sii_regional_office:
            raise UserError(_(
                'There is no SII Regional Office configured in your company. This is mandatory for electronic '
                'invoicing. Please go to your company and set the regional office, according to your company '
                'address (www.sii.cl - Mi SII)'))
        if self.l10n_latam_document_type_id.code == '39':
            if self.line_ids.filtered(lambda x: x.tax_group_id.id in [
                self.env['account.chart.template'].with_company(self.company_id).ref('tax_group_ila').id,
                self.env['account.chart.template'].with_company(self.company_id).ref('tax_group_retenciones').id,
            ]):
                raise UserError(_('Receipts with withholding taxes are not allowed'))
            if self.company_id.currency_id != self.currency_id:
                raise UserError(_('It is not allowed to create receipts in a different currency than CLP'))
        if (self.l10n_latam_document_type_id.code not in ['39', '41', '110', '111', '112'] and
                not (self.partner_id.l10n_cl_activity_description or
                     self.commercial_partner_id.l10n_cl_activity_description)):
            raise UserError(_(
                'There is not an activity description configured in the '
                'customer %s record. This is mandatory for electronic invoicing for this type of '
                'document. Please go to the partner record and set the activity description') % self.partner_id.name)
        if not self.l10n_latam_document_type_id._is_doc_type_electronic_ticket() and not self.partner_id.street:
            raise UserError(_(
                'There is no address configured in your customer %s record. '
                'This is mandatory for electronic invoicing for this type of document. '
                'Please go to the partner record and set the address') % self.partner_id.name)
        if (self.l10n_latam_document_type_id.code in ['34', '41', '110', '111', '112'] and
                self.amount_untaxed != self.amount_total):
            raise UserError(_('It seems that you are using items with taxes in exempt documents in invoice %(invoice_id)s - %(invoice_name)s.'
                              ' You must either:\n'
                              '   - Change the document type to a not exempt type.\n'
                              '   - Set an exempt fiscal position to remove taxes automatically.\n'
                              '   - Use products without taxes.\n'
                              '   - Remove taxes from product lines.', invoice_id=self.id, invoice_name=self.name))
        if self.l10n_latam_document_type_id.code == '33' and self.amount_untaxed == self.amount_total:
            raise UserError(_('All the items you are billing in invoice %(invoice_id)s - %(invoice_name)s, have no taxes.\n'
                              ' If you need to bill exempt items you must either use exempt invoice document type (34),'
                              ' or at least one of the items should have vat tax.', invoice_id=self.id, invoice_name=self.name))

    def _l10n_cl_get_sii_reception_status_message(self, sii_response_status):
        """
        Get the value of the code returns by SII once the DTE has been sent to the SII.
        """
        return {
            '0': _('Upload OK'),
            '1': _('Sender Does Not Have Permission To Send'),
            '2': _('File Size Error (Too Big or Too Small)'),
            '3': _('Incomplete File (Size <> Parameter size)'),
            '5': _('Not Authenticated'),
            '6': _('Company Not Authorized to Send Files'),
            '7': _('Invalid Schema'),
            '8': _('Document Signature'),
            '9': _('System Locked'),
            'Otro': _('Internal Error'),
        }.get(sii_response_status, sii_response_status)

    def _l10n_cl_get_sii_reception_status_message_rest(self, sii_response_status):
        return {
            'REC': _lt('Submission received'),
            'EPR': _lt('Submission processed'),
            'CRT': _lt('Cover OK'),
            'FOK': _lt('Submission signature validated'),
            'PRD': _lt('Submission in process'),
            'RCH': _lt('Rejected due to information errors'),
            'RCO': _lt('Rejected for consistency'),
            'VOF': _lt('The .xml file was not found'),
            'RFR': _lt('Rejected due to error in signature'),
            'RPR': _lt('Accepted with objections'),
            'RPT': _lt('Repeat submission rejected'),
            'RSC': _lt('Rejected by schema'),
            'SOK': _lt('Validated schema'),
            'RCT': _lt('Rejected by error in covert'),
        }.get(sii_response_status, sii_response_status)

    def _l10n_cl_get_verify_status_msg_rest(self, data):
        msg = _('Asking for DTE status with response:')
        if self.l10n_cl_dte_status in ['rejected', 'objected']:
            detail = data['detalle_rep_rech']
            if detail:
                msg += Markup('<br/><li><b>ESTADO</b>: %s</li>') % detail[0]['estado']
                errors = detail[0].get('error', [])
                for error in errors:
                    msg += Markup('<br/><li><b>ERROR</b>: %s %s</li>') % (error['descripcion'], error['detalle'] or "")
                return msg

        return msg + Markup('<br/><li><b>ESTADO</b>: %s</li>') % data['estado']

    def _l10n_cl_normalize_currency_name(self, currency_name):
        currency_dict = {
            'AED': 'DIRHAM',
            'ARS': 'PESO',
            'AUD': 'DOLAR AUST',
            'BOB': 'BOLIVIANO',
            'BRL': 'CRUZEIRO REAL',
            'CAD': 'DOLAR CAN',
            'CHF': 'FRANCO SZ',
            'CLP': 'PESO CL',
            'CNY': 'RENMINBI',
            'COP': 'PESO COL',
            'ECS': 'SUCRE',
            'EUR': 'EURO',
            'GBP': 'LIBRA EST',
            'HKD': 'DOLAR HK',
            'INR': 'RUPIA',
            'JPY': 'YEN',
            'MXN': 'PESO MEX',
            'NOK': 'CORONA NOR',
            'NZD': 'DOLAR NZ',
            'PEN': 'NUEVO SOL',
            'PYG': 'GUARANI',
            'SEK': 'CORONA SC',
            'SGD': 'DOLAR SIN',
            'TWD': 'DOLAR TAI',
            'USD': 'DOLAR USA',
            'UYU': 'PESO URUG',
            'VEF': 'BOLIVAR',
            'ZAR': 'RAND',
        }
        return currency_dict.get(currency_name, 'OTRAS MONEDAS')

    def _l10n_cl_get_dte_barcode_xml(self):
        """
        This method create the "stamp" (timbre). Is the auto-contained information inside the pdf417 barcode, which
        consists of a reduced xml version of the invoice, containing: issuer, recipient, folio and the first line
        of the invoice, etc.
        :return: xml that goes embedded inside the pdf417 code
        """
        dd = self.env['ir.qweb']._render('l10n_cl_edi.dd_template', {
            'move': self,
            'format_vat': self._l10n_cl_format_vat,
            'float_repr': float_repr,
            'format_length': self._format_length,
            'format_uom': self._format_uom,
            'time_stamp': self._get_cl_current_strftime(),
            'caf': self.l10n_latam_document_type_id._get_caf_file(
                self.company_id.id, int(self.l10n_latam_document_number)),
            'amounts': self._l10n_cl_get_amounts(),
            '__keep_empty_lines': True,
        })
        caf_file = self.l10n_latam_document_type_id._get_caf_file(
            self.company_id.id, int(self.l10n_latam_document_number))
        ted = self.env['ir.qweb']._render('l10n_cl_edi.ted_template', {
            'dd': dd,
            'frmt': self.env['certificate.key']._sign_with_key(
                re.sub(b'\n\\s*', b'', dd.encode('ISO-8859-1', 'replace')),
                base64.b64encode(caf_file.findtext('RSASK').encode('utf-8')),
                hashing_algorithm='sha1',
                formatting='base64',
            ).decode(),
            'stamp': self._get_cl_current_strftime(),
            '__keep_empty_lines': True,
        })
        return {
            'ted': Markup(re.sub(r'\n\s*$', '', ted, flags=re.MULTILINE)),
            'barcode': etree.tostring(etree.fromstring(re.sub(
                r'<TmstFirma>.*</TmstFirma>', '', ted), parser=etree.XMLParser(remove_blank_text=True)))
        }

    def _l10n_cl_get_reverse_doc_type(self):
        if self.partner_id.l10n_cl_sii_taxpayer_type == '4' or self.partner_id.country_id.code != "CL":
            return self.env['l10n_latam.document.type'].search(
                [('code', '=', '112'), ('country_id.code', '=', "CL")], limit=1)
        return self.env['l10n_latam.document.type'].search(
            [('code', '=', '61'), ('country_id.code', '=', "CL")], limit=1)

    def _l10n_cl_get_comuna_recep(self, recep=True):
        if self.partner_id._l10n_cl_is_foreign():
            if recep:
                return self._format_length(
                    self.partner_id.state_id.name or self.commercial_partner_id.state_id.name or 'N-A', 20)
            return self._format_length(self.partner_shipping_id.state_id.name or 'N-A', 20)
        if self.l10n_latam_document_type_id._is_doc_type_voucher():
            return 'N-A'
        if recep:
            return self._format_length(self.partner_id.city or self.commercial_partner_id.city, 20) or False
        return self._format_length(self.partner_shipping_id.city, 20) or False

    def _l10n_cl_get_set_dte_id(self, xml_content):
        set_dte = xml_content.find('.//ns0:SetDTE', namespaces={'ns0': 'http://www.sii.cl/SiiDte'})
        if set_dte is None:
            return ''
        return set_dte.attrib.get('ID')

    def _l10n_cl_get_report_base_filename(self):
        return _("%s COPY", self._get_report_base_filename())

    # Cron methods

    def _l10n_cl_ask_dte_status(self):
        for move in self.search([('l10n_cl_dte_status', '=', 'ask_for_status')]):
            move.l10n_cl_verify_dte_status(send_dte_to_partner=False)
            self.env.cr.commit()

    def _l10n_cl_send_dte_to_partner_multi(self):
        for move in self.search([('l10n_cl_dte_status', '=', 'accepted'),
                                 ('l10n_cl_dte_partner_status', '=', 'not_sent'),
                                 ('partner_id.country_id.code', '=', "CL")]):
            _logger.debug('Sending %s DTE to partner' % move.name)
            if move.partner_id._l10n_cl_is_foreign():
                continue
            move._l10n_cl_send_dte_to_partner()
            self.env.cr.commit()

    def _l10n_cl_ask_claim_status(self):
        for move in self.search([('l10n_cl_dte_acceptation_status', 'in', ['accepted', 'claimed']),
                                 ('move_type', 'in', ['out_invoice', 'out_refund']),
                                 ('l10n_cl_claim', '=', False)]):
            if move.company_id.l10n_cl_dte_service_provider in ['SIITEST', 'SIIDEMO']:
                continue
            move.l10n_cl_verify_claim_status()
            self.env.cr.commit()

    def _pdf417_barcode(self, barcode_data):
        #  This method creates the graphic representation of the barcode
        barcode_file = BytesIO()
        if pdf417gen is None:
            return False
        bc = pdf417gen.encode(barcode_data, security_level=5, columns=13)
        image = pdf417gen.render_image(bc, padding=15, scale=1)
        image.save(barcode_file, 'PNG')
        data = barcode_file.getvalue()
        return base64.b64encode(data)

    # cron jobs
    def cron_run_sii_workflow(self):
        """
        This method groups all the steps needed to do the SII workflow:
        1.- Ask to SII for the status of the DTE sent
        2.- Send to the customer the DTE accepted by the SII
        3.- Ask the status of the DTE claimed by the customer
        """
        _logger.debug('Starting cron SII workflow')
        self_skip = self.with_context(cron_skip_connection_errs=True)
        self_skip._l10n_cl_ask_dte_status()
        self_skip._l10n_cl_send_dte_to_partner_multi()
        self_skip._l10n_cl_ask_claim_status()

    def cron_send_dte_to_sii(self):
        for record in self.search([('l10n_cl_dte_status', '=', 'not_sent')]):
            record.with_context(cron_skip_connection_errs=True).l10n_cl_send_dte_to_sii()
            self.env.cr.commit()

    # ------------------------------------------------------------
    # IMPORT
    # ------------------------------------------------------------

    def _get_import_file_type(self, file_data):
        """ Identify DTE files. """
        # EXTENDS 'account'
        if file_data['xml_tree'] is not None and file_data['xml_tree'].xpath('//ns0:DTE', namespaces=XML_NAMESPACES):
            return 'l10n_cl.dte'

        return super()._get_import_file_type(file_data)

    def _unwrap_attachment(self, file_data, recurse=True):
        """ Divide a DTE into constituent invoices and create a new attachment for each invoice after the first. """
        # EXTENDS 'account'
        if file_data['import_file_type'] != 'l10n_cl.dte':
            return super()._unwrap_attachment(file_data, recurse)

        embedded = self._split_xml_into_new_attachments(file_data, tag='DTE')
        if embedded and recurse:
            embedded.extend(self._unwrap_attachments(embedded, recurse=True))
        return embedded

    def _get_edi_decoder(self, file_data, new=True):
        # EXTENDS 'account'
        if file_data['import_file_type'] == 'l10n_cl.dte':
            return {
                'priority': 20,
                'decoder': self._l10n_cl_import_dte,
            }
        return super()._get_edi_decoder(file_data, new=new)

    def _l10n_cl_import_dte(self, invoice, file_data, new):
        if invoice.invoice_line_ids:
            return invoice._reason_cannot_decode_has_invoice_lines()

        xml_tree = file_data['xml_tree']
        invoice.l10n_cl_dte_file = file_data['attachment']
        invoice.l10n_cl_dte_acceptation_status = 'received'

        vals = {}
        messages = []

        origin_type = self.env['fetchmail.server']._get_xml_origin_type(xml_tree)
        if origin_type == 'not_classified':
            messages.append(_('Failed to determine origin type of the attached document, attempting to process as a vendor bill'))

        invoice._l10n_cl_fill_partner_vals_from_xml(xml_tree, vals, messages)
        invoice._l10n_cl_fill_document_number_vals_from_xml(xml_tree, vals, messages)
        invoice._l10n_cl_fill_document_vals_from_xml(xml_tree, vals, messages)
        invoice._l10n_cl_fill_lines_vals_from_xml(xml_tree, vals, messages)
        invoice._l10n_cl_fill_references_vals_from_xml(xml_tree, vals, messages)

        invoice.message_post(body=Markup('<br/>').join(messages))
        invoice.write(vals)

        invoice._l10n_cl_adjust_manual_taxes_from_xml(xml_tree)
        invoice._l10n_cl_check_total_amount_from_xml(xml_tree)

    def _l10n_cl_fill_partner_vals_from_xml(self, xml_tree, vals, messages):
        partner_vat = (
            xml_tree.findtext('.//ns0:RUTEmisor', namespaces=XML_NAMESPACES).upper() or
            xml_tree.findtext('.//ns0:RutEmisor', namespaces=XML_NAMESPACES).upper()
        )
        if partner_vat and (partner := self.env['res.partner'].search(
            [
                ("vat", "=", partner_vat),
                *self.env['res.partner']._check_company_domain(self.company_id.id),
            ],
            limit=1,
        )):
            vals['partner_id'] = partner.id
            return

        partner_name = xml_tree.findtext('.//ns0:RznSoc', namespaces=XML_NAMESPACES)
        partner_street = xml_tree.findtext('.//ns0:DirOrigen', namespaces=XML_NAMESPACES)

        if partner_name and partner_vat and partner_street:
            with contextlib.suppress(ValidationError):
                vals['partner_id'] = self.env['res.partner'].create({
                    'name': partner_name,
                    'vat': partner_vat,
                    'street': partner_street,
                    'country_id': self.env.ref('base.cl').id,
                    'l10n_latam_identification_type_id': self.env.ref('l10n_cl.it_RUT').id,
                    'l10n_cl_sii_taxpayer_type': '1'
                }).id
                return

        vals['narration'] = partner_vat

        msg = Markup(
            '%(explanation)s<br/>'
            '<li><b>%(name_l)s</b>: %(name)s</li>'
            '<li><b>%(rut_l)s</b>: %(rut)s</li>'
            '<li><b>%(address_l)s</b>: %(address)s</li>'
        ) % {
            'explanation': _('Vendor not found: You can generate this vendor manually with the following information:'),
            'name_l': _("Name"), 'name': partner_name or '',
            'rut_l': _("RUT"), 'rut': partner_vat or '',
            'address_l': _("Address"), 'address': partner_street or ''
        }
        messages.append(msg)

    def _l10n_cl_fill_document_number_vals_from_xml(self, xml_tree, vals, messages):
        document_number = xml_tree.findtext('.//ns0:Folio', namespaces=XML_NAMESPACES)
        document_type_code = xml_tree.findtext('.//ns0:TipoDTE', namespaces=XML_NAMESPACES)
        document_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', document_type_code), ('country_id.code', '=', 'CL')], limit=1,
        )
        if not document_type:
            messages.append(_('Document type %s not found.', document_type_code))
        if document_type.internal_type not in ['invoice', 'debit_note', 'credit_note']:
            messages.append(_('The document type %s is not a vendor bill.', document_type_code))

        if vals.get('partner_id'):
            duplicate_domain = [('partner_id', '=', vals['partner_id'])]
        else:
            duplicate_domain = [
                ('partner_id', '=', False),
                ('narration', '=', vals['narration']),
            ]
        if self.search([
            *duplicate_domain,
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('name', 'ilike', document_number),
            ('l10n_latam_document_type_id', '=', document_type.id),
            *self.env['account.move']._check_company_domain(self.company_id.id),
        ]).filtered(lambda m: m.l10n_latam_document_number.lstrip('0') == document_number.lstrip('0')):
            messages.append(_('E-invoice already exist: %s', document_number))

        if document_type_code == '61':
            vals['move_type'] = 'in_refund'
        vals['l10n_latam_document_type_id'] = document_type
        vals['l10n_latam_document_number'] = document_number

    def _l10n_cl_fill_document_vals_from_xml(self, xml_tree, vals, messages):
        invoice_date = xml_tree.findtext('.//ns0:FchEmis', namespaces=XML_NAMESPACES)
        if invoice_date is not None:
            vals['invoice_date'] = fields.Date.from_string(invoice_date)

        vals['date'] = fields.Date.context_today(
            self.with_context(tz='America/Santiago')
        )

        invoice_date_due = xml_tree.findtext('.//ns0:FchVenc', namespaces=XML_NAMESPACES)
        if invoice_date_due is not None:
            vals['invoice_date_due'] = fields.Date.from_string(invoice_date_due)

        currency_name = xml_tree.findtext('.//ns0:Moneda', namespaces=XML_NAMESPACES) or 'CLP'
        if currency_name.isnumeric():
            currency_name = CURRENCY_CODES.get(currency_name)
        if currency := self.env['res.currency'].with_context(active_test=False).search([('name', '=', currency_name)]):
            vals['currency_id'] = currency
        else:
            vals['currency_id'] = self.env.ref('base.CLP')

    def _l10n_cl_fill_lines_vals_from_xml(self, xml_tree, vals, messages):
        vals['invoice_line_ids'] = [
            Command.create(line_vals)
            for line_vals in self._l10n_cl_get_lines_vals_from_xml(xml_tree, vals, messages)
        ]

    def _l10n_cl_get_lines_vals_from_xml(self, xml_tree, vals, messages):
        """
        This parse DTE invoice detail lines and tries to match lines with existing products.
        If no products are found, it puts only the description of the products in the draft invoice lines
        """
        gross_amount = xml_tree.findtext('.//ns0:MntBruto', namespaces=XML_NAMESPACES) is not None
        use_default_tax = xml_tree.findtext('.//ns0:TasaIVA', namespaces=XML_NAMESPACES) is not None
        default_purchase_tax = self.env['account.chart.template'].ref('OTAX_19')
        currency = vals['currency_id']
        lines_vals_list = []
        for dte_line in xml_tree.findall('.//ns0:Detalle', namespaces=XML_NAMESPACES):
            product_code = dte_line.findtext('.//ns0:VlrCodigo', namespaces=XML_NAMESPACES)
            product_name = dte_line.findtext('.//ns0:NmbItem', namespaces=XML_NAMESPACES)
            product = self._l10n_cl_get_vendor_product(product_code, product_name, self.company_id, vals.get('partner_id'))
            # the QtyItem tag is not mandatory in certain cases (case 2 in documentation).
            # Should be set to 1 if not present.
            # See http://www.sii.cl/factura_electronica/formato_dte.pdf row 15 and row 22 of tag table
            quantity = float(dte_line.findtext('.//ns0:QtyItem', default=1, namespaces=XML_NAMESPACES))
            # in the same case, PrcItem is not mandatory if QtyItem is not present, but MontoItem IS mandatory
            # this happens whenever QtyItem is not present in the invoice.
            # See http://www.sii.cl/factura_electronica/formato_dte.pdf row 38 of tag table.
            qty1 = quantity or 1
            price_unit = float(dte_line.findtext('.//ns0:MontoItem', default=0, namespaces=XML_NAMESPACES)) / qty1
            # See http://www.sii.cl/factura_electronica/formato_dte.pdf,
            # where MontoItem is defined as (price_unit * quantity ) - discount + surcharge
            # The amount present in "MontoItem" contains
            # the value with discount or surcharge applied, so we don't need to calculate it, just dividing this amount
            # by the quantity we get the price unit we should use in Odoo.
            if dte_line.findtext('.//ns0:IndExe', namespaces=XML_NAMESPACES) == '6':
                # If the exempt code is '6' the amount is negative
                price_unit = -price_unit
            line_vals = {
                'product_id': product.id,
                'name': product.name if product else dte_line.findtext('.//ns0:NmbItem', namespaces=XML_NAMESPACES),
                'quantity': quantity,
                'price_unit': price_unit,
                'tax_ids': [],
            }
            if (xml_tree.findtext('.//ns0:TasaIVA', namespaces=XML_NAMESPACES) is not None and
                    dte_line.findtext('.//ns0:IndExe', namespaces=XML_NAMESPACES) is None):
                taxes = self._l10n_cl_get_default_tax(product) or default_purchase_tax
                withholding_tax_codes = [int(element.text) for element in dte_line.findall('.//ns0:CodImpAdic', namespaces=XML_NAMESPACES)]
                withholding_taxes = self.env['account.tax'].search([
                    *self.env['account.tax']._check_company_domain(self.company_id),
                    ('type_tax_use', '=', 'purchase'),
                    ('l10n_cl_sii_code', 'in', withholding_tax_codes)
                ])
                line_vals['tax_ids'] = [Command.set(taxes.ids + withholding_taxes.ids)]
            if gross_amount:
                # in case the tag MntBruto is included in the IdDoc section, and there are not
                # additional taxes (withholdings)
                # even if the company has not selected its default tax value, we deduct it
                # from the price unit, gathering the value rate of the l10n_cl default purchase tax
                line_vals['price_unit'] = default_purchase_tax.with_context(
                 force_price_include=True).compute_all(price_unit, currency)['total_excluded']
            lines_vals_list.append(line_vals)

        for desc_rcg_global in xml_tree.findall('.//ns0:DscRcgGlobal', namespaces=XML_NAMESPACES):
            line_type = desc_rcg_global.findtext('.//ns0:TpoMov', namespaces=XML_NAMESPACES)
            price_type = desc_rcg_global.findtext('.//ns0:TpoValor', namespaces=XML_NAMESPACES)
            discount_surcharge_value = (desc_rcg_global.findtext('.//ns0:ValorDROtrMnda', namespaces=XML_NAMESPACES) or
                        desc_rcg_global.findtext('.//ns0:ValorDR', namespaces=XML_NAMESPACES))
            line_vals = {
                'name': 'DESCUENTO' if line_type == 'D' else 'RECARGO',
                'quantity': 1,
                'tax_ids': [],
            }
            amount_dr = float(discount_surcharge_value)
            percent_dr = amount_dr / 100
            # The price unit of a discount line should be negative while surcharge should be positive
            price_unit_multiplier = 1 if line_type == 'D' else -1
            if price_type == '%':
                inde_exe_dr = desc_rcg_global.findtext('.//ns0:IndExeDR', namespaces=XML_NAMESPACES)
                if inde_exe_dr is None:  # Applied to items with tax
                    dte_amount_tag = (xml_tree.findtext('.//ns0:MntNetoOtrMnda', namespaces=XML_NAMESPACES) or
                                      xml_tree.findtext('.//ns0:MntNeto', namespaces=XML_NAMESPACES))
                    dte_amount = int(dte_amount_tag or 0)
                    # as MntNeto value is calculated after discount
                    # we need to calculate back the amount before discount in order to apply the percentage
                    # and know the amount of the discount.
                    dte_amount_before_discount = dte_amount / (1 - percent_dr)
                    line_vals['price_unit'] = - price_unit_multiplier * dte_amount_before_discount * percent_dr
                    if use_default_tax:
                        line_vals['tax_ids'] = [Command.link(default_purchase_tax.id)]
                elif inde_exe_dr == '2':  # Applied to items not billable
                    dte_amount_tag = xml_tree.findtext('.//ns0:MontoNF', namespaces=XML_NAMESPACES)
                    dte_amount = dte_amount_tag is not None and int(dte_amount_tag) or 0
                    line_vals['price_unit'] = round(
                        dte_amount - (int(dte_amount) / (1 - amount_dr / 100))) * price_unit_multiplier
                elif inde_exe_dr == '1':  # Applied to items without taxes
                    dte_amount_tag = (xml_tree.findtext('.//ns0:MntExeOtrMnda', namespaces=XML_NAMESPACES) or
                                      xml_tree.findtext('.//ns0:MntExe', namespaces=XML_NAMESPACES))
                    dte_amount = dte_amount_tag is not None and int(dte_amount_tag) or 0
                    line_vals['price_unit'] = round(
                        dte_amount - (int(dte_amount) / (1 - amount_dr / 100))) * price_unit_multiplier
            else:
                if gross_amount:
                    amount_dr = default_purchase_tax.with_context(force_price_include=True).compute_all(
                        amount_dr, currency)['total_excluded']
                line_vals['price_unit'] = amount_dr * -1 * price_unit_multiplier
                if use_default_tax and desc_rcg_global.findtext('.//ns0:IndExeDR', namespaces=XML_NAMESPACES) not in ['1', '2']:
                    line_vals['tax_ids'] = [Command.link(default_purchase_tax.id)]

            lines_vals_list.append(line_vals)
        return lines_vals_list

    def _l10n_cl_get_default_tax(self, product):
        return product.taxes_id.filtered(lambda tax: tax.company_id == self.company_id and tax.type_tax_use == 'purchase')

    def _l10n_cl_get_vendor_product(self, product_code, product_name, company_id, partner_id):
        """
        This tries to match products specified in the vendor bill with current products in database.
        Criteria to attempt a match with existent products:
        1) check if product_code in the supplier info is present (if partner_id is established)
        2) if (1) fails, check if product supplier info name is present (if partner_id is established)
        3) if (1) and (2) fail, check product default_code
        4) if 3 previous criteria fail, check product name, and return false if fails
        """
        if partner_id:
            supplier_info_domain = [
                *self.env['product.supplierinfo']._check_company_domain(company_id),
                ('partner_id', '=', partner_id),
            ]
            if product_code:
                # 1st criteria
                supplier_info_domain.append(('product_code', '=', product_code))
            else:
                # 2nd criteria
                supplier_info_domain.append(('product_name', '=', product_name))
            supplier_info = self.env['product.supplierinfo'].sudo().search(supplier_info_domain, limit=1)
            if supplier_info:
                return supplier_info.product_id
        # 3rd criteria
        if product_code:
            product = self.env['product.product'].sudo().search([
                *self.env['product.product']._check_company_domain(company_id),
                '|', ('default_code', '=', product_code), ('barcode', '=', product_code),
            ], limit=1)
            if product:
                return product
        # 4th criteria
        return self.env['product.product'].sudo().search([
            *self.env['product.product']._check_company_domain(company_id),
            ('name', 'ilike', product_name),
        ], limit=1)

    def _l10n_cl_fill_references_vals_from_xml(self, xml_tree, vals, messages):
        vals['l10n_cl_reference_ids'] = [
            Command.create(reference_line)
            for reference_line in self._l10n_cl_get_invoice_references_from_xml(xml_tree)
        ]

    def _l10n_cl_get_invoice_references_from_xml(self, xml_tree):
        invoice_reference_ids = []
        for reference in xml_tree.findall('.//ns0:Referencia', namespaces=XML_NAMESPACES):
            new_reference = {
                'origin_doc_number': reference.findtext('.//ns0:FolioRef', namespaces=XML_NAMESPACES),
                'reference_doc_code': reference.findtext('.//ns0:CodRef', namespaces=XML_NAMESPACES),
                'reason': reference.findtext('.//ns0:RazonRef', namespaces=XML_NAMESPACES),
                'date': reference.findtext('.//ns0:FchRef', namespaces=XML_NAMESPACES),
            }
            if reference_doc_type_code := reference.findtext('.//ns0:TpoDocRef', namespaces=XML_NAMESPACES):
                if reference_doc_type := self.env['l10n_latam.document.type'].search(
                    [('code', '=', reference_doc_type_code)], limit=1
                ):
                    new_reference['l10n_cl_reference_doc_type_id'] = reference_doc_type.id
                else:
                    new_reference['reason'] = '%s: %s' % (reference_doc_type_code, new_reference['reason'])
            invoice_reference_ids.append(new_reference)
        return invoice_reference_ids

    def _l10n_cl_adjust_manual_taxes_from_xml(self, xml_tree):
        """
        This method adjusts values on automatically created tax lines for taxes with manually read amounts from the imported XML
        It should work for other properly setup taxes read from the <ImptoReten> section when their codes are added to the list
        """
        if xml_tree.findtext('.//ns0:ImptoReten', namespaces=XML_NAMESPACES) is not None:
            manual_tax_lines = self._l10n_cl_get_manual_taxes_from_xml(xml_tree)
        else:
            return
        line_ids_command = []
        processed_sii_codes = set()
        for sii_code in manual_tax_lines:
            sii_code_lines = self.line_ids.filtered(lambda aml: aml.tax_line_id.l10n_cl_sii_code == sii_code)
            if len(sii_code_lines) != 1:
                # Found more than one tax line corresponding to a manual import SII code, ignoring
                processed_sii_codes.add(sii_code)
        sign = -1 if self.is_inbound() else 1
        delta_payment_term = 0.0
        for line in self.line_ids:
            sii_code = line.tax_line_id.l10n_cl_sii_code
            if sii_code in (35, 28) and sii_code not in processed_sii_codes:
                processed_sii_codes.add(sii_code)
                new_amount_currency = sign * manual_tax_lines[sii_code]
                delta = new_amount_currency - line.amount_currency
                delta_payment_term -= delta
                line_ids_command.append(Command.update(line.id, {'amount_currency': new_amount_currency}))
        payment_term = self.line_ids.filtered(lambda aml: aml.display_type == 'payment_term')[:1]
        if not payment_term or not processed_sii_codes:
            return
        line_ids_command.append(Command.update(payment_term.id, {'amount_currency': payment_term.amount_currency + delta_payment_term}))
        self.line_ids = line_ids_command

    def _l10n_cl_get_manual_taxes_from_xml(self, xml_tree):
        """
        Get information for lines of manually-read taxes from the values listed in ImptoReten elements
        """
        tipo_list = [int(element.text) for element in xml_tree.findall('.//ns0:TipoImp', namespaces=XML_NAMESPACES)]
        monto_list = [float(element.text) for element in xml_tree.findall('.//ns0:MontoImp', namespaces=XML_NAMESPACES)]
        manual_tax_lines = {}
        for tipo, monto in zip(tipo_list, monto_list):
            manual_tax_lines[tipo] = monto
        return manual_tax_lines

    def _l10n_cl_check_total_amount_from_xml(self, xml_tree):
        xml_total_amount = float(xml_tree.findtext('.//ns0:MntTotal', namespaces=XML_NAMESPACES))
        if self.currency_id.compare_amounts(self.amount_total, xml_total_amount) != 0:
            self.message_post(
                body=Markup("<strong> %s </strong> %s") % (
                        _("Warning:"),
                        _("The total amount of the DTE\'s XML is %(xml_amount)s and the total amount calculated by Odoo is %(move_amount)s. Typically this is caused by additional lines in the detail or by unidentified taxes, please check if a manual correction is needed.",
                            xml_amount=formatLang(self.env, xml_total_amount, currency_obj=self.currency_id),
                            move_amount=formatLang(self.env, self.amount_total, currency_obj=self.currency_id)
                        )
                    )
                )
