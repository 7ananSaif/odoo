# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import email
import logging
import os

from lxml import etree

from xmlrpc import client as xmlrpclib

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

XML_NAMESPACES = {
    'ns0': 'http://www.sii.cl/SiiDte',
    'ns1': 'http://www.w3.org/2000/09/xmldsig#',
    'xml_schema': 'http://www.sii.cl/XMLSchema'
}

DEFAULT_DOC_NUMBER_PADDING = 6


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    l10n_cl_is_dte = fields.Boolean(
        'DTE server', help='By checking this option, this email account will be used to receive the electronic\n'
                           'invoices from the suppliers, and communications from the SII regarding the electronic\n'
                           'invoices issued. In this case, this email should match both emails declared on the SII\n'
                           'site in the section: "ACTUALIZACION DE DATOS DEL CONTRIBUYENTE", "Mail Contacto SII"\n'
                           'and "Mail Contacto Empresas".')
    l10n_cl_last_uid = fields.Integer(
        string='Last read message ID (CL)', default=1,
        help='This value is pointing to the number of the last message read by odoo '
             'in the inbox. This value will be updated by the system during its normal'
             'operation.')

    @api.constrains('l10n_cl_is_dte', 'server_type')
    def _check_server_type(self):
        for record in self:
            if record.l10n_cl_is_dte and record.server_type not in ('imap', 'outlook', 'gmail'):
                raise ValidationError(_('The server must be of type IMAP.'))

    def _fetch_mail(self, **kw):
        # TODO This reimplements the logic from the mail module to connect to a
        # server, we should instead handle the message in `mail.thread.message_process`.
        # The logic seems to have drifted away, even before refactoring to use `commit_progress`.
        for server in self.filtered(lambda s: s.l10n_cl_is_dte):
            if not server.try_lock_for_update():
                continue

            _logger.info('Start checking for new emails on %s IMAP server %s', server.server_type, server.name)

            # prevents the process from timing out when connecting for the first time
            # to an edi email server with too many new emails to process
            # e.g over 5k emails. We will only fetch the next 50 "new" emails
            # based on their IMAP uid
            default_batch_size = kw.get('batch_limit') or 50

            fetched_messages = []
            imap_server = None
            try:
                imap_server = server._connect__()
                imap_server.select()

                result, data = imap_server.uid('search', None, '(UID %s:*)' % server.l10n_cl_last_uid)
                new_max_uid = server.l10n_cl_last_uid
                for uid in data[0].split()[:default_batch_size]:
                    if int(uid) <= server.l10n_cl_last_uid:
                        # We get always minimum 1 message.  If no new message, we receive the newest already managed.
                        continue

                    result, data = imap_server.uid('fetch', uid, '(RFC822)')

                    if not data[0]:
                        continue
                    message = data[0][1]

                    # To leave the mail in the state in which they were.
                    if 'Seen' not in data[1].decode('UTF-8'):
                        imap_server.uid('STORE', uid, '+FLAGS', '(\\Seen)')
                    else:
                        imap_server.uid('STORE', uid, '-FLAGS', '(\\Seen)')

                    # See details in message_process() in mail_thread.py
                    if isinstance(message, xmlrpclib.Binary):
                        message = bytes(message.data)
                    if isinstance(message, str):
                        message = message.encode('utf-8')
                    fetched_messages.append((uid, message))

            except Exception:  # noqa: BLE001
                _logger.info(
                    'General failure when trying to fetch mail from %s server %s.',
                    server.server_type,
                    server.name,
                    exc_info=True,
                )
            finally:
                if imap_server:
                    try:
                        imap_server.close()
                        imap_server.logout()
                    except Exception:  # noqa: BLE001
                        _logger.warning('Failed to properly finish connection: %s.', server.name, exc_info=True)

            for uid, message in fetched_messages:
                msg_txt = email.message_from_bytes(message, policy=email.policy.SMTP)

                # Because `_extend_with_attachments` (called by `_process_incoming_email`)
                # commits the cursor, any failure will not rollback any invoice that
                # is already successfully decoded.
                server._process_incoming_email(msg_txt)
                new_max_uid = max(new_max_uid, int(uid))
                server.write({'l10n_cl_last_uid': new_max_uid})

            _logger.info('Fetched %d email(s) on %s server %s.', len(fetched_messages), server.server_type, server.name)

            server.write({'date': fields.Datetime.now()})
            self.env.cr.commit()
        return super(FetchmailServer, self.filtered(lambda s: not s.l10n_cl_is_dte))._fetch_mail(**kw)

    def _process_incoming_email(self, msg_txt):
        parsed_values = self.env['mail.thread']._message_parse_extract_payload(msg_txt, {})
        body, attachments = parsed_values['body'], parsed_values['attachments']
        from_address = msg_txt.get('from')
        for attachment in attachments:
            _logger.info('Processing attachment %s' % attachment.fname)
            attachment_ext = os.path.splitext(attachment.fname)[1]
            format_content = attachment.content.encode() if isinstance(attachment.content, str) else attachment.content
            if attachment_ext.lower() != '.xml' or not self._is_dte_email(format_content):
                _logger.info('Attachment %s has been discarded! It is not a xml file or is not a DTE email' %
                             attachment.fname)
                continue
            xml_tree = etree.fromstring(format_content)
            origin_type = self._get_xml_origin_type(xml_tree)
            if origin_type == 'not_classified':
                _logger.info('Attachment %s has been discarded! Origin type: %s' % (attachment.fname, origin_type))
                continue
            company = self._get_dte_recipient_company(xml_tree, origin_type)
            if not company or not self._is_dte_enabled_company(company):
                _logger.info('Attachment %s has been discarded! It is not a valid company (id: %s)' % (
                    attachment.fname, company.id))
                continue
            file_data = {
                'name': attachment.fname,
                'raw': format_content,
                'xml_tree': xml_tree,
            }
            if origin_type == 'incoming_supplier_document':
                moves = self._process_incoming_supplier_document(file_data, from_address, company.id)
                for move in moves:
                    if move.partner_id:
                        try:
                            move._l10n_cl_send_receipt_acknowledgment()
                        except UserError as error:
                            move.message_post(body=str(error))
            elif origin_type == 'incoming_sii_dte_result':
                self._process_incoming_sii_dte_result(file_data)
            elif origin_type in ['incoming_acknowledge', 'incoming_commercial_accept', 'incoming_commercial_reject']:
                self._process_incoming_customer_claim(company.id, file_data, origin_type)

    def _process_incoming_supplier_document(self, file_data, from_address, company_id):
        attachment = self.env['ir.attachment'].create({'name': file_data['name'], 'raw': file_data['raw']})

        # This will separate each DTE into a new attachment, and create a move for each DTE and call the decoder.
        moves = self.env['account.move'].with_context(
            default_invoice_source_email=from_address,
            default_move_type='in_invoice',
            default_company_id=company_id,
            default_journal_id=self.env['account.journal'].search(
                [
                    *self.env['account.journal']._check_company_domain(company_id),
                    ('type', '=', 'purchase'),
                    ('l10n_latam_use_documents', '=', True),
                ],
                limit=1,
            ),
        )._create_records_from_attachments(attachment)

        _logger.info('Draft vendor bills with ids: %s have been filled from DTE %s', moves.ids, file_data['name'])
        return moves

    def _process_incoming_sii_dte_result(self, file_data):
        xml_tree = file_data['xml_tree']
        track_id = xml_tree.findtext('.//TRACKID').zfill(10)
        moves = self.env['account.move'].search([('l10n_cl_sii_send_ident', '=', track_id)])
        status = xml_tree.findtext('IDENTIFICACION/ESTADO')
        error_status = xml_tree.findtext('REVISIONENVIO/REVISIONDTE/ESTADO')
        if error_status is not None:
            msg = _('Incoming SII DTE result:<br/> '
                    '<li><b>ESTADO</b>: %(status)s</li>'
                    '<li><b>REVISIONDTE/ESTADO</b>: %(error_status)s</li>'
                    '<li><b>REVISIONDTE/DETALLE</b>: %(details)s</li>',
                      status=status, error_status=error_status, details=xml_tree.findtext('REVISIONENVIO/REVISIONDTE/DETALLE'))
        else:
            msg = _('Incoming SII DTE result:<br/><li><b>ESTADO</b>: %s</li>', status)
        for move in moves:
            move.message_post(body=msg)

    def _process_incoming_customer_claim(self, company_id, file_data, origin_type):
        dte_tag = 'RecepcionDTE' if origin_type == 'incoming_acknowledge' else 'ResultadoDTE'
        xml_tree = file_data['xml_tree']
        for dte in xml_tree.xpath('//ns0:%s' % dte_tag, namespaces=XML_NAMESPACES):
            document_number = dte.findtext('.//ns0:Folio', namespaces=XML_NAMESPACES)
            partner_vat = (
                dte.findtext('.//ns0:RUTRecep', namespaces=XML_NAMESPACES).upper() or
                dte.findtext('.//ns0:RutReceptor', namespaces=XML_NAMESPACES).upper()
            )
            if not (partner := self.env["res.partner"].search([
                ("vat", "=", partner_vat),
                *self.env['res.partner']._check_company_domain(company_id),
            ], limit=1)):
                _logger.warning('Partner for incoming customer claim has not been found for %s', partner_vat)
                continue
            document_type_code = dte.findtext('.//ns0:TipoDTE', namespaces=XML_NAMESPACES)
            document_type = self.env['l10n_latam.document.type'].search(
                [('code', '=', document_type_code), ('country_id.code', '=', 'CL')], limit=1)
            move = self.env['account.move'].sudo().search([
                ('partner_id', '=', partner.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('l10n_latam_document_type_id', '=', document_type.id),
                ('l10n_cl_dte_status', '=', 'accepted'),
                ('name', '=ilike', f'{document_type.doc_code_prefix}%{document_number}'),
                ('company_id', '=', company_id),
            ]).filtered(lambda m: m.name.split()[1].lstrip('0') == document_number)

            if not move:
                _logger.warning('Move not found with partner: %s, document_number: %s, l10n_latam_document_type: %s, '
                              'company_id: %s', partner.id, document_number, document_type.id, company_id)
                continue

            if len(move) > 1:
                _logger.warning('Multiple moves found for partner: %s, document_number: %s, l10n_latam_document_type: %s, '
                            'company_id: %s. Expected only one move.', partner.id, document_number, document_type.id, company_id)
                continue

            status = {'incoming_acknowledge': 'received', 'incoming_commercial_accept': 'accepted'}.get(
                origin_type, 'claimed')
            move.write({'l10n_cl_dte_acceptation_status': status})
            move.message_post(
                body=_('DTE reception status established as <b>%s</b> by incoming email', status),
                attachments=[(file_data['name'], file_data['raw'])])

    def _is_dte_email(self, attachment_content):
        return b'http://www.sii.cl/SiiDte' in attachment_content or b'<RESULTADO_ENVIO>' in attachment_content

    def _get_dte_recipient_company(self, xml_tree, origin_type):
        xml_tag_by_type = {
            'incoming_supplier_document': '//ns0:RutReceptor',
            'incoming_sii_dte_result': '//RUTEMISOR',
            'incoming_acknowledge': '//ns0:RutRecibe',
            'incoming_commercial_accept': '//ns0:RutRecibe',
            'incoming_commercial_reject': '//ns0:RutRecibe',
        }
        receiver_rut = xml_tree.xpath(
            xml_tag_by_type.get(origin_type), namespaces=XML_NAMESPACES)
        if not receiver_rut:
            return None
        return self.env['res.company'].sudo().search([('vat', '=', receiver_rut[0].text)], limit=1)

    def _is_dte_enabled_company(self, company):
        return False if not company.l10n_cl_dte_service_provider else True

    def _get_xml_origin_type(self, xml_tree):
        tag = etree.QName(xml_tree.tag).localname
        if tag == 'EnvioDTE':
            return 'incoming_supplier_document'
        if tag == 'RespuestaDTE':
            if xml_tree.findtext('.//ns0:EstadoRecepDTE', namespaces=XML_NAMESPACES) == '0':
                return 'incoming_acknowledge'
            if xml_tree.findtext('.//ns0:EstadoDTE', namespaces=XML_NAMESPACES) == '0':
                return 'incoming_commercial_accept'
            return 'incoming_commercial_reject'
        if tag == 'RESULTADO_ENVIO':
            return 'incoming_sii_dte_result'
        return 'not_classified'
