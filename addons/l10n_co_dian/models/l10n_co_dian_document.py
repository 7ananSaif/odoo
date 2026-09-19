from base64 import b64encode, b64decode
from datetime import datetime
from lxml import etree
from lxml.etree import CDATA
from markupsafe import Markup

from odoo import api, fields, models, modules
from odoo.tools import html_escape, cleanup_xml_node, date_utils
from odoo.addons.l10n_co_dian import xml_utils
from odoo.exceptions import UserError

EVENT_FILE_SEQUENCE_CODE = "l10n_co_dian_file_sequence_code"

COMMERCIAL_STATE_SELECTION = [
    ('pending', "Pending"),
    ('received', "030 - Received"),
    ('goods_received', "032 - Goods Received"),
    ('claimed', "031 - Claimed"),
    ('accepted', "033 - Accepted by Customer"),
    ('accepted_by_issuer', "034 - Accepted by Issuer"),
]


class L10n_Co_DianDocument(models.Model):
    _name = 'l10n_co_dian.document'
    _description = "Colombian documents used for each interaction with the DIAN"
    _order = 'datetime DESC, id DESC'

    # Relational fields
    attachment_id = fields.Many2one(comodel_name='ir.attachment')
    move_id = fields.Many2one(comodel_name='account.move')

    # Business fields
    identifier = fields.Char(string="CUFE/CUDE/CUDS")
    zip_key = fields.Char(
        help="ID returned by the DIAN when sending a document with the certification process activated."
    )  # ID returned when calling SendTestSetAsync
    state = fields.Selection(selection=[
        ('invoice_sending_failed', "Sending Failed"),  # webservice is not reachable
        ('invoice_pending', "Pending"),  # document was sent and the response is not yet known
        ('invoice_rejected', "Rejected"),
        ('invoice_accepted', "Accepted"),
    ])
    message_json = fields.Json()
    message = fields.Html(compute="_compute_message")
    datetime = fields.Datetime()
    test_environment = fields.Boolean(help="Indicates whether the test endpoint was used to send this document")
    certification_process = fields.Boolean(
        help="Indicates whether we were in the certification process when sending this document",
    )
    commercial_state = fields.Selection(
        selection=COMMERCIAL_STATE_SELECTION,
        string="Commercial Status"
    )

    # Buttons
    show_button_get_status = fields.Boolean(compute="_compute_show_button_get_status")
    show_button_fetch_attached_document = fields.Boolean(compute='_compute_show_button_fetch_attached_document')

    @api.depends('zip_key', 'state', 'test_environment', 'certification_process')
    def _compute_show_button_get_status(self):
        for doc in self:
            doc.show_button_get_status = (
                doc.zip_key
                and doc.state not in ('invoice_accepted', 'invoice_rejected')
                and doc.test_environment
                and doc.certification_process
            )

    @api.depends('attachment_id', 'move_id.move_type')
    def _compute_show_button_fetch_attached_document(self):
        for doc in self:
            doc.show_button_fetch_attached_document = doc.attachment_id and doc.move_id.move_type not in ('in_invoice', 'in_refund')

    @api.depends('message_json')
    def _compute_message(self):
        for doc in self:
            msg = html_escape(doc.message_json.get('status', ""))
            if doc.message_json.get('errors'):
                msg += Markup("<ul>{errors}</ul>").format(
                    errors=Markup().join(
                        Markup("<li>%s</li>") % error for error in doc.message_json['errors']
                    ),
                )
            doc.message = msg

    def unlink(self):
        self.attachment_id.unlink()
        return super().unlink()

    @api.model
    def _parse_errors(self, root):
        """ Returns a list containing the errors/warnings from a DIAN response """
        return [node.text for node in root.findall(".//{*}ErrorMessage/{*}string")]

    @api.model
    def _build_message(self, root):
        msg = {'status': False, 'errors': []}
        fault = root.find('.//{*}Fault/{*}Reason/{*}Text')
        if fault is not None and fault.text:
            msg['status'] = fault.text + " (This might be caused by using incorrect certificates)"
        status = root.find('.//{*}StatusDescription')
        if status is not None and status.text:
            msg['status'] = status.text
        msg['errors'] = self._parse_errors(root)
        return msg

    @api.model
    def _create_document(self, xml, move, state, **kwargs):
        move.ensure_one()

        root = etree.fromstring(xml)
        demo_mode = move.company_id.l10n_co_dian_demo_mode
        attachment_name = kwargs.pop('attachment_name', None) or self.env['account.edi.xml.ubl_dian']._export_invoice_filename(move)

        if demo_mode:
            doc_datetime = datetime.now()
        elif 'datetime' in kwargs:
            doc_datetime = kwargs.pop('datetime')
        else:
            # naive local colombian datetime
            doc_datetime = date_utils.to_timezone(None)(datetime.fromisoformat(root.find('.//{*}SigningTime').text))

        if demo_mode:
            identifier = 'DEMO'
        elif 'identifier' in kwargs:
            identifier = kwargs.pop('identifier')
        else:
            identifier = root.find('.//{*}UUID').text

        # create document
        doc = self.create([{
            'move_id': move.id,
            'identifier': identifier,
            'state': state,
            'datetime': doc_datetime,
            'test_environment': move.company_id.l10n_co_dian_test_environment,
            'certification_process': move.company_id.l10n_co_dian_certification_process,
            **kwargs,
        }])

        if state == 'invoice_accepted' and not doc.commercial_state:
            doc.commercial_state = 'pending'

        # create attachment
        doc.attachment_id = self.env['ir.attachment'].create([{
            'raw': xml,
            'name': attachment_name,
            'res_id': doc.id if state != 'invoice_accepted' else move.id,
            'res_model': doc._name if state != 'invoice_accepted' else move._name,
        }])

        return doc

    @api.model
    def _document_already_processed(self, response_element):
        """
        This function checks if a response contains a specific error that DIAN
        returns when a document has already been sent and processed.
        :param response_element: etree.Element
        """
        is_valid = response_element.findtext('.//{*}IsValid') == 'true'
        response_status_code = response_element.findtext('.//{*}StatusCode')

        if not is_valid and response_status_code == '99':
            errors = response_element.findall(".//{*}ErrorMessage/{*}string")
            return len(errors) == 1 and errors[0].text == 'Regla: 90, Rechazo: Documento procesado anteriormente.'

        return False

    @api.model
    def _send_test_set_async(self, zipped_content, move):
        """ Send the document to the 'SendTestSetAsync' (asynchronous) webservice.
        NB: later, need to fetch the result by calling the 'GetStatusZip' webservice.
        """
        operation_mode = self.env['account.edi.xml.ubl_dian']._dian_get_operation_mode(move)
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'file_name': "invoice.zip",
                'content_file': b64encode(zipped_content).decode(),
                'test_set_id': operation_mode.dian_testing_id,
                'soap_body_template': "l10n_co_dian.send_test_set_async",
            },
            service="SendTestSetAsync",
            company=move.company_id,
        )
        if not response['response']:
            return {
                'state': 'invoice_sending_failed',
                'message_json': {'status': self.env._("The DIAN server did not respond.")},
            }
        root = etree.fromstring(response['response'])
        if response['status_code'] != 200:
            return {
                'state': 'invoice_sending_failed',
                'message_json': self._build_message(root),
            }
        zip_key = root.findtext('.//{*}ZipKey')
        if zip_key:
            return {
                'state': 'invoice_pending',
                'message_json': {'status': self.env._("Invoice is being processed by the DIAN.")},
                'zip_key': zip_key,
            }
        return {
            'state': 'invoice_rejected',
            'message_json': {'errors': [node.text for node in root.findall('.//{*}ProcessedMessage')]},
        }

    @api.model
    def _send_bill_sync(self, zipped_content, move):
        """ Send the document to the 'SendBillSync' (synchronous) webservice. """

        if move.company_id.l10n_co_dian_demo_mode:
            return {
                'state': 'invoice_accepted',
                'message_json': {'status': self.env._("Demo mode response")},
            }

        response = xml_utils._build_and_send_request(
            self,
            payload={
                'file_name': "invoice.zip",
                'content_file': b64encode(zipped_content).decode(),
                'soap_body_template': "l10n_co_dian.send_bill_sync",
            },
            service="SendBillSync",
            company=move.company_id,
        )
        if not response['response']:
            return {
                'state': 'invoice_sending_failed',
                'message_json': {'status': self.env._("The DIAN server did not respond.")},
            }
        root = etree.fromstring(response['response'])
        if response['status_code'] != 200:
            return {
                'state': 'invoice_sending_failed',
                'message_json': self._build_message(root),
            }

        is_valid = root.findtext('.//{*}IsValid') == 'true'
        document_vals = {
            'state': 'invoice_accepted' if is_valid else 'invoice_rejected',
            'message_json': self._build_message(root),
        }

        if self._document_already_processed(root) and (identifier := root.findtext('.//{*}XmlDocumentKey')):
            # Document has already been processed by DIAN -> correctly set the identifier and state so GetStatus is called correctly
            document_vals |= {
                'state': 'invoice_accepted',
                'identifier': identifier,
            }

        return document_vals

    @api.model
    def _send_event_update_status(self, zipped_content, move, next_commercial_state):
        if move.company_id.l10n_co_dian_demo_mode:
            return {
                'state': 'invoice_accepted',
                'commercial_state': next_commercial_state,
                'message_json': {'status': self.env._("Demo mode response")},
            }, dict()

        response = xml_utils._build_and_send_request(
            self,
            payload={
                'content_file': b64encode(zipped_content).decode(),
                'soap_body_template': "l10n_co_dian.send_event_update_status",
            },
            service="SendEventUpdateStatus",
            company=move.company_id,
        )

        if not response['response']:
            return {
                'state': 'invoice_sending_failed',
                'message_json': {'status': self.env._("The DIAN server did not respond.")},
            }, None

        root = etree.fromstring(response['response'])
        state = 'invoice_rejected'

        if response['status_code'] != 200:
            state = 'invoice_sending_failed'
        elif root.findtext('.//{*}IsValid') == 'true':
            state = 'invoice_accepted'

        document_vals = {
            'state': state,
            'commercial_state': next_commercial_state,
            'message_json': self._build_message(root),
        }

        if self._document_already_processed(root):
            # DIAN rejected this call because it already accepted a call with the next commercial state
            # so we can safely force the state to accepted so the user can continue the commercial event flow
            document_vals['state'] = 'invoice_accepted'

        return document_vals, response

    @api.model
    def _get_status_event(self, company_id, track_id):
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': track_id,
                'soap_body_template': "l10n_co_dian.get_status_event",
            },
            service="GetStatusEvent",
            company=company_id,
        )

        if not response['response']:
            return {
                'state': 'invoice_sending_failed',
                'message_json': {'status': self.env._("The DIAN server did not respond.")},
            }, None

        root = etree.fromstring(response['response'])
        state = 'invoice_rejected'

        if response['status_code'] != 200:
            state = 'invoice_sending_failed'
        elif root.findtext('.//{*}IsValid') == 'true':
            state = 'invoice_accepted'

        return {
            'state': state,
            'message_json': self._build_message(root),
        }, response

    def _get_status_zip(self):
        """ Fetch the status of a document sent to 'SendTestSetAsync' using the 'GetStatusZip' webservice. """
        self.ensure_one()
        response = xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': self.zip_key,
                'soap_body_template': "l10n_co_dian.get_status_zip",
            },
            service="GetStatusZip",
            company=self.move_id.company_id,
        )
        if response['status_code'] == 200:
            root = etree.fromstring(response['response'])
            self.message_json = self._build_message(root)
            if root.findtext('.//{*}IsValid') == 'true':
                self.state = 'invoice_accepted'
            elif not root.findtext('.//{*}StatusCode'):
                self.state = 'invoice_pending'
            else:
                self.state = 'invoice_rejected'
        elif response['status_code']:
            raise UserError(self.env._("The DIAN server returned an error (code %s)", response['status_code']))
        else:
            raise UserError(self.env._("The DIAN server did not respond."))

    def _get_status(self):
        return xml_utils._build_and_send_request(
            self,
            payload={
                'track_id': self.identifier,
                'soap_body_template': "l10n_co_dian.get_status",
            },
            service="GetStatus",
            company=self.move_id.company_id,
        )

    def _get_attached_document_values(self, original_xml_etree, response_history):
        values = {
            'profile_execution_id': original_xml_etree.findtext('./{*}ProfileExecutionID'),
            'id': original_xml_etree.findtext('./{*}ID'),
            'uuid': self[-1].identifier,
            'uuid_attrs': {
                'scheme_name': self[-1].move_id.l10n_co_dian_identifier_type.upper() + "-SHA384",
            },
            'issue_date': original_xml_etree.findtext('./{*}IssueDate'),
            'issue_time': original_xml_etree.findtext('./{*}IssueTime'),
            'document_type': "Contenedor de Factura Electrónica",
            'parent_document_id': original_xml_etree.findtext('./{*}ID'),
            'parent_documents': [],
        }

        for idx, event_xml in enumerate(response_history, start=1):
            event_tree = etree.fromstring(event_xml)
            values['parent_documents'].append({
                'id': idx,
                'uuid': self[-idx].identifier,
                'uuid_attrs': {
                    'scheme_name': self[-idx].move_id.l10n_co_dian_identifier_type.upper() + "-SHA384",
                },
                'issue_date': event_tree.findtext('./{*}IssueDate'),
                'issue_time': event_tree.findtext('./{*}IssueTime'),
                'response_code': event_tree.findtext('.//{*}Response/{*}ResponseCode'),
                'validation_date': event_tree.findtext('./{*}IssueDate'),
                'validation_time': event_tree.findtext('./{*}IssueTime'),
            })

        return values

    def _demo_get_attached_document_values(self, original_xml_etree):
        # Demo mode version: use all values that do not require a DIAN response
        return {
            'profile_execution_id': original_xml_etree.findtext('./{*}ProfileExecutionID'),
            'id': original_xml_etree.findtext('./{*}ID'),
            'uuid': self[-1].identifier,
            'uuid_attrs': {
                'scheme_name': self[-1].move_id.l10n_co_dian_identifier_type.upper() + "-SHA384",
            },
            'issue_date': original_xml_etree.findtext('./{*}IssueDate'),
            'issue_time': original_xml_etree.findtext('./{*}IssueTime'),
            'document_type': "Contenedor de Factura Electrónica",
            'parent_document_id': original_xml_etree.findtext('./{*}ID'),
            'parent_document': {
                'id': original_xml_etree.findtext('./{*}ID'),
                'uuid': self[-1].identifier,
                'uuid_attrs': {
                    'scheme_name': self[-1].move_id.l10n_co_dian_identifier_type.upper() + "-SHA384",
                },
                'issue_date': 'Demo',
                'issue_time': 'Demo',
                'response_code': 'Demo',
                'validation_date': 'Demo',
                'validation_time': 'Demo',
            },
        }

    def _get_response_history(self, current_response=None):
        """
        Return the responses of all the documents in 'self'
        """
        if self.move_id.company_id.l10n_co_dian_demo_mode:
            return [etree.fromstring('<ApplicationResponse></ApplicationResponse>')]

        if not current_response:
            # Should not enter this if statement when handling Commercial Events
            # call to GetStatus to get the ApplicationResponse
            current_response = self._get_status()
            if current_response['status_code'] != 200:
                return "", self.env._(
                    "Error %(code)s when calling the DIAN server: %(response)s",
                    code=current_response['status_code'],
                    response=current_response['response'],
                )

        current_response_etree = etree.fromstring(current_response['response'])
        current_response_raw = b64decode(current_response_etree.findtext(".//{*}XmlBase64Bytes"))
        history = [current_response_raw]

        # exclude the first and last documents:
        # last: its xml has already been added to the history in the above section
        # first: is a dummy document created by Odoo which represents the 'pending' state before
        #        the commercial event flow has started, its xml should therefore not be added to the history
        for document in self.sorted()[1:-1]:
            # Unzip attachment -> return the event xml from the AttachedDocument (in the last ParentDocumentLineReference)
            attached_document = etree.fromstring(xml_utils._unzip(document.attachment_id.raw))
            document_line_ref = attached_document.findall('./{*}ParentDocumentLineReference')[-1]
            document_event_xml = document_line_ref.findtext('.//{*}Description').encode()
            history.append(document_event_xml)

        return history

    def _get_attached_document(self, status_response=None):
        """ Return a tuple: (the attached document xml, an error message) """
        if self.move_id.l10n_co_dian_commercial_state == 'pending':
            # ensure_one for moves != ('in_invoice', 'in_refund') or when no event has been sent yet
            self.ensure_one()

        # all event xml's for every document in self in order
        response_history = self._get_response_history(current_response=status_response)
        current_attachment_raw = self[-1].attachment_id.raw
        original_xml_etree = etree.fromstring(current_attachment_raw)

        if self.move_id.company_id.l10n_co_dian_demo_mode:
            vals = self._demo_get_attached_document_values(original_xml_etree=original_xml_etree)
        else:
            vals = self._get_attached_document_values(
                original_xml_etree=original_xml_etree,
                response_history=response_history,
            )

        attached_document = self.env['ir.qweb']._render('l10n_co_dian.attached_document', vals)
        attached_doc_etree = etree.fromstring(attached_document)

        # copy the Sender and Receiver from the original xml
        supplier_node = original_xml_etree.find('./{*}AccountingSupplierParty//{*}PartyTaxScheme')
        if supplier_node is None:
            supplier_node = original_xml_etree.find('./{*}SenderParty//{*}PartyTaxScheme')

        customer_node = original_xml_etree.find('./{*}AccountingCustomerParty//{*}PartyTaxScheme')
        if customer_node is None:
            customer_node = original_xml_etree.find('./{*}ReceiverParty//{*}PartyTaxScheme')

        attached_doc_etree.find('./{*}SenderParty').append(supplier_node)
        attached_doc_etree.find('./{*}ReceiverParty').append(customer_node)

        # Add the xmls (enclosed in CDATA)
        attached_doc_etree.find('./{*}Attachment/{*}ExternalReference/{*}Description').text = CDATA(current_attachment_raw.decode(encoding='unicode_escape'))
        for idx, event_xml in enumerate(response_history, start=1):
            document_element = attached_doc_etree.find(f'./{{*}}ParentDocumentLineReference/{{*}}LineID[.="{idx}"]/..')

            if document_element is not None:
                # Roundtrip it through etree to remove the XML declaration (<?xml version="1.0" encoding="utf-8"...)
                event_xml = etree.tostring(etree.fromstring(event_xml), encoding='unicode')
                document_element.find('.//{*}Description').text = CDATA(event_xml)

        return etree.tostring(cleanup_xml_node(attached_doc_etree), encoding="UTF-8", xml_declaration=True), ""

    def action_get_attached_document(self):
        self.ensure_one()
        attached_document, error = self._get_attached_document()
        if error:
            raise UserError(error)
        attachment = self.env['ir.attachment'].create({
            'raw': attached_document,
            'name': self.move_id._l10n_co_dian_get_attached_document_filename() + '_manual.xml',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
        }

    @api.model
    def _send_to_dian(self, xml, move):
        """ Send an xml to DIAN.
        If the Certification Process is activated, use the dedicated 'SendTestSetAsync' (asynchronous) webservice,
        otherwise, use the 'SendBillSync' (synchronous) webservice.

        :return: a l10n_co_dian.document
        """
        # Zip the xml
        zipped_content = xml_utils._zip_xml('invoice', xml)

        if move.company_id.l10n_co_dian_test_environment and move.company_id.l10n_co_dian_certification_process:
            document_vals = self._send_test_set_async(zipped_content, move)
        else:
            document_vals = self._send_bill_sync(zipped_content, move)
        return self._create_document(xml, move, **document_vals)

    @api.model
    def _send_commercial_event(self, move, commercial_state_next):
        locked_move = move.try_lock_for_update()
        if not locked_move:
            return self.env['l10n_co_dian.document']

        xml, errors = self.env['account.edi.xml.ubl_dian']._export_co_send_event_update_status_invoice(locked_move, commercial_state_next)
        if errors:
            raise UserError(self.env._("Error(s) while generating the UBL file:\n- %s", '\n- '.join(errors)))

        locked_move.l10n_co_dian_document_ids.filtered(lambda doc: doc.state == 'invoice_rejected').unlink()

        filename = locked_move._l10n_co_dian_get_commercial_event_document_filename('zip')
        zipped_content = xml_utils._zip_xml(filename, xml)

        document_vals, response = self._send_event_update_status(zipped_content, locked_move, commercial_state_next)
        document = self._create_document(xml, move, **document_vals)

        if document.state != 'invoice_accepted':
            # reset the filename sequence
            sequence = self.env['ir.sequence'].search([('code', '=', EVENT_FILE_SEQUENCE_CODE), ('company_id', '=', self.move_id.company_id.id)])
            sequence.number_next = sequence.number_next - 1

            return document

        attached_document_xml, error = move.l10n_co_dian_document_ids._get_attached_document(response)
        if error:
            raise UserError(error)

        attached_document = self.env['ir.attachment'].create([{
            'raw': attached_document_xml,
            'name': f"{filename}.xml",
            'res_model': 'l10n_co_dian.document',
            'res_id': document.id,
        }])

        attached_document_zip = self.env['ir.attachment'].create([{
            'name': f"{filename}.zip",
            'raw': attached_document._build_zip_from_attachments(),
            'res_model': 'l10n_co_dian.document',
            'res_id': document.id,
        }])

        attached_document.unlink()  # was only necessary to build the zip file
        document.attachment_id.unlink()  # _create_document sets the attachment_id to the sent xml file

        document.attachment_id = attached_document_zip
        if not modules.module.current_test:
            self.env.cr.commit()
        return document

    @api.model
    def _send_get_status_event(self, move, track_id):
        if move.company_id.l10n_co_dian_demo_mode:
            return

        document_vals, response = self._get_status_event(move.company_id, track_id)
        if not response:
            raise UserError('\n- '.join(document_vals['message_json']['errors']))

        date_time = datetime.now()
        document = self._create_document(response['response'], move, identifier=track_id, datetime=date_time, **document_vals)
        if document.state != 'invoice_accepted':
            return

        document_xml = b64decode(etree.fromstring(response['response']).findtext('.//{*}XmlBase64Bytes'))

        # Get the commercial state
        root = etree.fromstring(document_xml)
        last_response = root.findall('.//{*}DocumentResponse')[-1]
        commercial_status_code = last_response.findtext('./{*}Response/{*}ResponseCode')

        document.attachment_id.raw = document_xml

        commercial_states = self.env['account.move']._fields['l10n_co_dian_commercial_state']._description_selection(self.env)
        commercial_state = next(k for k, v in commercial_states if v.split(' - ', 1)[0] == commercial_status_code)
        document.commercial_state = commercial_state

    def action_get_status(self):
        for doc in self:
            doc._get_status_zip()

    def action_download_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
        }
