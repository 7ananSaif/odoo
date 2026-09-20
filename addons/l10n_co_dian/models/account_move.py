from pytz import timezone
from lxml import etree

from collections import defaultdict
from datetime import datetime, timedelta
import re

from odoo import api, fields, models, modules
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.addons.l10n_co_dian import xml_utils
from odoo.addons.l10n_co_dian.models.l10n_co_dian_document import COMMERCIAL_STATE_SELECTION, EVENT_FILE_SEQUENCE_CODE


DESCRIPTION_CREDIT_CODE = [
    ("1", "Devolución parcial de los bienes y/o no aceptación parcial del servicio"),
    ("2", "Anulación de factura electrónica"),
    ("3", "Rebaja total aplicada"),
    ("4", "Ajuste de precio"),
    ("5", "Descuento comercial por pronto pago"),
    ("6", "Descuento comercial por volumen de ventas")
]

DESCRIPTION_DEBIT_CODE = [
    ('1', 'Intereses'),
    ('2', 'Gastos por cobrar'),
    ('3', 'Cambio del valor'),
    ('4', 'Otros'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_co_dian_show_support_doc_button = fields.Boolean(compute='_compute_l10n_co_dian_show_support_doc_button')
    l10n_co_dian_post_time = fields.Datetime(readonly=True, copy=False)

    l10n_co_dian_document_ids = fields.One2many(
        comodel_name='l10n_co_dian.document',
        inverse_name='move_id',
    )
    l10n_co_edi_cufe_cude_ref = fields.Char(
        string="CUFE/CUDE/CUDS",
        compute='_compute_l10n_co_dian_cufe',
        store=True,
        readonly=True,
        copy=False,
        help="Unique ID used by the DIAN to identify the invoice.",
    )
    l10n_co_dian_state = fields.Selection(
        selection=[
            ('invoice_sending_failed', "Sending Failed"),
            ('invoice_pending', "Pending"),
            ('invoice_rejected', "Rejected"),
            ('invoice_accepted', "Accepted"),
        ],
        compute='_compute_l10n_co_dian_states',
        store=True,
        copy=False,
    )
    l10n_co_dian_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute='_compute_l10n_co_dian_attachment_id',
    )
    l10n_co_dian_identifier_type = fields.Selection(
        selection=[
            ('cufe', 'CUFE'),
            ('cude', 'CUDE'),
            ('cuds', 'CUDS'),
        ],
        compute="_compute_l10n_co_dian_identifier_type",
    )
    l10n_co_dian_is_enabled = fields.Boolean(compute="_compute_l10n_co_dian_is_enabled")
    l10n_co_dian_processed_by_get_event_status_cron = fields.Boolean()
    l10n_co_dian_commercial_state = fields.Selection(
        string="Commercial Status",
        default='pending',
        selection=COMMERCIAL_STATE_SELECTION,
        compute='_compute_l10n_co_dian_states',
        copy=False,
        store=True,
    )

    l10n_co_dian_claim_reason = fields.Selection(
        string="Claim Reason",
        selection=[
            ('01', "Document with inconsistencies"),
            ('02', "Undelivered merchandise"),
            ('03', "Merchandise partially delivered"),
            ('04', "Service not provided"),
        ],
        copy=False,
    )

    l10n_co_dian_update_commercial_event_enabled = fields.Boolean(compute='_compute_l10n_co_dian_update_commercial_event_enabled')

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends(
        'move_type',
        'l10n_co_edi_is_support_document',
        'l10n_co_dian_document_ids.state',
        'l10n_co_dian_document_ids.commercial_state',
    )
    def _compute_l10n_co_dian_cufe(self):
        for move in self:
            if move.move_type in ('in_invoice', 'in_refund') and not move.l10n_co_edi_is_support_document:
                move.l10n_co_edi_cufe_cude_ref = move.l10n_co_edi_cufe_cude_ref
                continue

            move.l10n_co_edi_cufe_cude_ref = move.l10n_co_edi_cufe_cude_ref

            documents = move.l10n_co_dian_document_ids.sorted()
            is_accepted_by_issuer = False
            for document in documents:
                if document.state not in ('invoice_pending', 'invoice_accepted'):
                    continue

                # In case a document has been accepted by the issuer, we report the identifier of the first send document when the
                # commercial state was pending.
                if document.commercial_state == 'accepted_by_issuer':
                    is_accepted_by_issuer = True
                if is_accepted_by_issuer and document.commercial_state == 'pending':
                    move.l10n_co_edi_cufe_cude_ref = document.identifier
                    break

                # Otherwise, report the identifier for the 'invoice_accepted' document.
                if not is_accepted_by_issuer and document.state == 'invoice_accepted':
                    move.l10n_co_edi_cufe_cude_ref = document.identifier
                    break

    @api.depends('l10n_co_dian_document_ids', 'l10n_co_dian_document_ids.state', 'l10n_co_dian_document_ids.commercial_state')
    def _compute_l10n_co_dian_states(self):
        for move in self:
            move.l10n_co_dian_commercial_state = False
            move.l10n_co_dian_state = False
            documents = move.l10n_co_dian_document_ids.sorted()
            for document in documents:
                if not move.l10n_co_dian_state:
                    move.l10n_co_dian_state = document.state
                if not move.l10n_co_dian_commercial_state and document.state == 'invoice_accepted':
                    move.l10n_co_dian_commercial_state = document.commercial_state

    @api.depends('l10n_co_dian_document_ids', 'l10n_co_dian_document_ids.state')
    def _compute_l10n_co_dian_attachment_id(self):
        for move in self:
            move.l10n_co_dian_attachment_id = False
            documents = move.l10n_co_dian_document_ids.sorted()
            for document in documents:
                if document.state == 'invoice_accepted':
                    move.l10n_co_dian_attachment_id = document.attachment_id
                    break

    @api.depends('journal_id', 'move_type')
    def _compute_l10n_co_dian_identifier_type(self):
        for move in self:
            if move.journal_id.l10n_co_edi_debit_note or move.move_type == 'out_refund':
                move.l10n_co_dian_identifier_type = 'cude'  # Debit Notes, Credit Notes
            elif move.l10n_co_edi_is_support_document:
                move.l10n_co_dian_identifier_type = 'cuds'  # Support Documents (Vendor Bills)
            else:
                move.l10n_co_dian_identifier_type = 'cufe'  # Invoices

    @api.depends('state', 'move_type', 'l10n_co_dian_state')
    def _compute_l10n_co_dian_show_support_doc_button(self):
        for move in self:
            move.l10n_co_dian_show_support_doc_button = (
                move.l10n_co_dian_is_enabled
                and move.l10n_co_dian_state != 'invoice_accepted'
                and move.move_type in ('in_refund', 'in_invoice')
                and move.state == 'posted'
                and move.journal_id.l10n_co_edi_is_support_document
            )

    @api.depends('country_code', 'company_currency_id', 'move_type', 'company_id.l10n_co_dian_provider')
    def _compute_l10n_co_dian_is_enabled(self):
        """ Check whether or not the DIAN is needed on this invoice. """
        for move in self:
            move.l10n_co_dian_is_enabled = (
                move.country_code == "CO"
                and move.company_currency_id.name == "COP"
                and move.is_invoice()
                and move.company_id.l10n_co_dian_provider == 'dian'
            )

    @api.depends('l10n_co_dian_document_ids.state', 'l10n_co_dian_commercial_state')
    def _compute_l10n_co_dian_update_commercial_event_enabled(self):
        for move in self:
            move.l10n_co_dian_update_commercial_event_enabled = (
                    any(doc.state == 'invoice_accepted' for doc in move.l10n_co_dian_document_ids)
                    and move.l10n_co_dian_commercial_state not in ('claimed', 'accepted', 'accepted_by_issuer')
            )

    # -------------------------------------------------------------------------
    # Extends
    # -------------------------------------------------------------------------

    def _post(self, soft=True):
        # EXTENDS account
        res = super()._post(soft=soft)
        for move in self.filtered('l10n_co_dian_is_enabled'):
            # naive local colombian datetime
            now = fields.Datetime.to_string(datetime.now(tz=timezone('America/Bogota')))
            move.l10n_co_dian_post_time = now

            if move.is_purchase_document() and not move.l10n_co_edi_is_support_document and not move.l10n_co_dian_document_ids:
                self.env['l10n_co_dian.document']._create_document(
                    '<Note>No xml</Note>',
                    move,
                    'invoice_accepted',
                    attachment_name=f'dian_{move.move_type}_{move.name}.xml',
                    commercial_state='pending',
                    message_json={'status': ''},
                    datetime=now,
                    identifier=move.l10n_co_edi_cufe_cude_ref,
                )
        return res

    @api.depends('l10n_co_dian_state')
    def _compute_show_reset_to_draft_button(self):
        # EXTENDS 'account'
        super()._compute_show_reset_to_draft_button()
        for move in self.filtered(lambda m: m.move_type == 'out_invoice'):
            # Reset to draft is not possible for invoices validated by DIAN
            if any(d.state in ('invoice_pending', 'invoice_accepted') and d.commercial_state == 'pending' for d in move.l10n_co_dian_document_ids):
                move.show_reset_to_draft_button = False

    def _get_name_invoice_report(self):
        # EXTENDS account
        self.ensure_one()
        if self.env.ref('l10n_co_dian.report_vendor_document', raise_if_not_found=False) and \
                self.l10n_co_edi_is_support_document and \
                self.move_type in ('in_refund', 'in_invoice'):
            return 'l10n_co_dian.report_vendor_document'
        elif self.l10n_co_dian_state == 'invoice_accepted' and self.l10n_co_dian_attachment_id:
            return 'l10n_co_dian.report_invoice_document'
        return super()._get_name_invoice_report()

    def _get_import_file_type(self, file_data):
        """ Identify DIAN UBL files. """
        # EXTENDS 'account'
        if (
            file_data['xml_tree'] is not None
            and (ubl_profile := file_data['xml_tree'].findtext('{*}ProfileID'))
            and ubl_profile.startswith('DIAN 2.1:')
        ):
            return 'account.edi.xml.ubl_dian'

        return super()._get_import_file_type(file_data)

    @api.model
    def _get_mail_template(self):
        # EXTENDS 'account'
        self.ensure_one()
        mail_template = super()._get_mail_template()
        if self.country_code == 'CO':
            xmlid = 'l10n_co_dian.email_template_edi_credit_note' if self.move_type == 'out_refund' else 'l10n_co_dian.email_template_edi_invoice'
            return self.env.ref(xmlid, raise_if_not_found=False) or mail_template
        return mail_template

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def l10n_co_dian_action_update_event_status(self):
        self.l10n_co_dian_document_ids.filtered(lambda doc: doc.state == 'invoice_rejected').unlink()

        for move in self.try_lock_for_update():
            track_id = move._l10n_co_dian_get_last_accepted_document().identifier
            if not track_id:
                continue

            self.env['l10n_co_dian.document']._send_get_status_event(move, track_id)
            if not modules.module.current_test:
                self.env.cr.commit()

            # unlink duplicate documents and only keep the most recent ones
            # for this process we exclude the original document containing the invoice data
            documents = self.l10n_co_dian_document_ids.sorted()[:-1]
            grouped_documents = documents.grouped(key='commercial_state')
            for commercial_state, duplicate_documents in grouped_documents.items():
                duplicate_documents.sorted()[1:].unlink()

    def l10n_co_dian_send_event_update_status_received(self):
        self._l10n_co_dian_send_event_update_status('received')

    def l10n_co_dian_send_event_update_status_claimed(self):
        self._l10n_co_dian_send_event_update_status('claimed')

    def l10n_co_dian_send_event_update_status_goods_received(self):
        self._l10n_co_dian_send_event_update_status('goods_received')

    def l10n_co_dian_send_event_update_status_accepted(self):
        self._l10n_co_dian_send_event_update_status('accepted')

    def l10n_co_dian_send_event_update_status_accepted_by_issuer(self):
        self._l10n_co_dian_send_event_update_status('accepted_by_issuer')

    def _l10n_co_dian_send_event_update_status(self, commercial_state_next):
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(self.env._("Only invoicing users can update the DIAN commercial status."))

        self.ensure_one()
        self._l10n_co_dian_validate_send_event_update_data()
        document = self.env['l10n_co_dian.document']._send_commercial_event(self, commercial_state_next)

        if document.state == 'invoice_accepted':
            # Send mail
            AccountMoveSend = self.env['account.move.send']
            mail_template = self.env.ref('l10n_co_dian.email_template_commercial_event')
            mail_lang = AccountMoveSend._get_default_mail_lang(self, mail_template)

            self.with_context(
                email_notification_allow_footer=True,
            ).message_post(
                message_type='comment',
                subtype_id=self.env.ref('mail.mt_comment').id,
                body=AccountMoveSend._get_default_mail_body(self, mail_template, mail_lang),
                subject=AccountMoveSend._get_default_mail_subject(self, mail_template, mail_lang),
                partner_ids=self.partner_id.ids,
                attachments=[(self.l10n_co_dian_attachment_id.name, self.l10n_co_dian_attachment_id.raw)],
            )

    def _l10n_co_dian_validate_send_event_update_data(self):
        errors = []
        # Validate required data for vendor bills
        if self.move_type in ('in_invoice', 'in_refund'):
            if not self.ref:
                errors.append(self.env._("The Bill Reference is required to send commercial events."))

            if not self.l10n_co_edi_cufe_cude_ref:
                errors.append(self.env._("The Bill CUFE/CUDE is required to send commercial events."))

        if errors:
            raise ValidationError('\n'.join(errors))

        # Validate required data for invoices and vendor bills
        if self.partner_id and not self.partner_id.vat:
            raise RedirectWarning(
                message=self.env._("The receiving partner's identification number is required to send commercial events."),
                action={
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'context': {'create': False},
                    'view_mode': 'form',
                    'views': [[self.env.ref('base.view_partner_form').id, 'form']],
                    'res_id': self.partner_id.id,
                },
                button_text=self.env._("Go to Partner"),
            )

    def _l10n_co_dian_get_mail_commercial_state_label(self):
        self.ensure_one()
        commercial_states = dict(self._fields['l10n_co_dian_commercial_state']._description_selection(self.with_context(lang=self.partner_id.lang).env))
        return commercial_states.get(self.l10n_co_dian_commercial_state, '')

    def _l10n_co_dian_get_electronic_document_number(self):
        self.ensure_one()
        if not self.l10n_co_dian_attachment_id:
            return None

        if self.move_type in ('in_invoice', 'in_refund') and not self.l10n_co_edi_is_support_document:
            root = etree.fromstring(xml_utils._unzip(self.l10n_co_dian_attachment_id.raw))
        else:
            root = etree.fromstring(self.l10n_co_dian_attachment_id.raw)

        nsmap = {k: v for k, v in root.nsmap.items() if k}  # empty namespace prefix is not supported for XPaths
        return root.findtext('./cbc:ID', namespaces=nsmap)

    def l10n_co_dian_action_send_bill_support_document(self):
        self.ensure_one()
        xml, errors = self.env['account.edi.xml.ubl_dian']._export_invoice(self)
        if errors:
            raise UserError(self.env._("Error(s) when generating the UBL attachment:\n- %s", '\n- '.join(errors)))
        doc = self._l10n_co_dian_send_invoice_xml(xml)
        if doc.state == 'invoice_rejected':
            if self.env['account.move.send']._can_commit():
                self.env.cr.commit()
            raise UserError(self.env._("Error(s) when sending the document to the DIAN:\n- %s",
                              "\n- ".join(doc.message_json['errors']) or doc.message_json['status']))

    def _l10n_co_dian_get_invoice_report_qr_code_value(self):
        """ Returns the value to be embedded inside the QR Code on the PDF report.
        For Support Documents, see section 12.2 ('Anexo-Tecnico-Documento-Soporte[...].pdf').
        Otherwise, see section 11.7 ('Anexo-Tecnico-[...]-1-9.pdf').
        """
        self.ensure_one()
        root = etree.fromstring(self.l10n_co_dian_attachment_id.raw)
        nsmap = {k: v for k, v in root.nsmap.items() if k}  # empty namespace prefix is not supported for XPaths
        supplier_company_id = root.findtext('./cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', namespaces=nsmap)
        customer_company_id = root.findtext('./cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID', namespaces=nsmap)
        line_extension_amount = root.findtext('./cac:LegalMonetaryTotal/cbc:LineExtensionAmount', namespaces=nsmap)
        tax_amount_01 = sum(float(x) for x in root.xpath('./cac:TaxTotal[.//cbc:ID/text()="01"]/cbc:TaxAmount/text()', namespaces=nsmap))
        payable_amount = root.findtext('./cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=nsmap)
        identifier = root.findtext('./cbc:UUID', namespaces=nsmap)
        qr_code = root.findtext('./ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/sts:DianExtensions/sts:QRCode', namespaces=nsmap)
        vals = {
            'NumDS': root.findtext('./cbc:ID', namespaces=nsmap),
            'FecFD': root.findtext('./cbc:IssueDate', namespaces=nsmap),
            'HorDS': root.findtext('./cbc:IssueTime', namespaces=nsmap),
        }
        if self.l10n_co_edi_is_support_document:
            vals.update({
                'NumSNO': supplier_company_id,
                'DocABS': customer_company_id,
                'ValDS': line_extension_amount,
                'ValIva': tax_amount_01,
                'ValTolDS': payable_amount,
                'CUDS': identifier,
                'QRCode': qr_code,
            })
        else:
            vals.update({
                'NitFac': supplier_company_id,
                'DocAdq': customer_company_id,
                'ValFac': line_extension_amount,
                'ValIva': tax_amount_01,
                'ValOtroIm': sum(float(x) for x in root.xpath('./cac:TaxTotal[.//cbc:ID/text()!="01"]/cbc:TaxAmount/text()', namespaces=nsmap)),
                'ValTolFac': payable_amount,
                'CUFE': identifier,
                'QRCode': qr_code,
            })
        return "\n".join(f"{k}: {v}" for k, v in vals.items())

    def _l10n_co_dian_get_extra_invoice_report_values(self):
        """ Get the values used to render the PDF """
        self.ensure_one()
        document = self._l10n_co_dian_get_last_accepted_document()
        return {
            'barcode_src': f'/report/barcode/?barcode_type=QR&value="{self._l10n_co_dian_get_invoice_report_qr_code_value()}"&width=180&height=180&quiet=0',
            'signing_datetime': document.datetime.replace(microsecond=0),
            'identifier': document.identifier,
        }

    def _l10n_co_dian_get_invoice_prepayments(self):
        """ Collect the prepayments linked to an account.move (based on the partials)
        :returns: a list of dict of the form: [{'name', 'amount', 'date'}]
        """
        if not self.is_sale_document():
            return []
        lines = self.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        prepayment_by_move = defaultdict(float)
        source_exchange_move = {}
        for field in ('debit', 'credit'):
            for partial in lines[f'matched_{field}_ids'].sorted('exchange_move_id.id'):
                counterpart_line = partial[f'{field}_move_id']
                # Aggregate the exchange difference amount
                if partial.exchange_move_id:
                    source_exchange_move[partial.exchange_move_id] = counterpart_line
                elif counterpart_line.move_id in source_exchange_move:
                    counterpart_line = source_exchange_move[counterpart_line.move_id]
                    if counterpart_line not in prepayment_by_move:
                        continue
                # Exclude the partials created after creating a credit note from an existing move
                if (
                    (counterpart_line.move_id.move_type == 'out_refund' and lines.move_type == 'out_invoice')
                    or (counterpart_line.move_id.move_type == 'out_invoice' and lines.move_type == 'out_refund')
                ):
                    continue
                prepayment_by_move[counterpart_line] += partial.amount
        return [
            {
                'name': line.name,
                'date': line.date,
                'amount': amount,
            }
            for line, amount in prepayment_by_move.items()
        ]

    def _l10n_co_dian_send_invoice_xml(self, xml):
        """ Main method called by the Send & Print wizard / on a Support Document
        It unlinks the previous rejected documents, create a new one, send it to DIAN and logs in the chatter
        if it is accepted.
        """
        self.ensure_one()
        self.l10n_co_dian_document_ids.filtered(lambda doc: doc.state == 'invoice_rejected').unlink()
        document = self.env['l10n_co_dian.document']._send_to_dian(xml=xml, move=self)
        if document.state == 'invoice_accepted':
            self.message_post(
                body=self.env._(
                    "The %s was accepted by the DIAN.",
                    dict(document.move_id._fields['move_type'].selection)[document.move_id.move_type],
                ) if not document.move_id.company_id.l10n_co_dian_demo_mode else self.env._(
                    "The %s was validated locally in Demo Mode.",
                    dict(document.move_id._fields['move_type'].selection)[document.move_id.move_type],
                ),
                attachment_ids=document.attachment_id.copy().ids,
            )
        return document

    def _l10n_co_dian_get_attached_document_filename(self):
        self.ensure_one()
        # remove every non-word char or underscore, keep only the alphanumeric characters
        return re.sub(r'[\W_]', '', self.name)

    def _l10n_co_dian_get_commercial_event_document_filename(self, file_ext):
        self.ensure_one()
        prefix = 'ar' if file_ext == 'xml' else 'z'
        vat = self.company_id.partner_id._get_vat_without_verification_code().zfill(10)
        year = fields.Datetime.now().strftime("%y")

        suffix = self.with_company(self.company_id).env['ir.sequence'].next_by_code(EVENT_FILE_SEQUENCE_CODE)
        if not suffix:
            sequence = self.env['ir.sequence'].sudo().create([{
                'name': f"Commercial Event File Name ({self.company_id.name})",
                'code': EVENT_FILE_SEQUENCE_CODE,
                'company_id': self.company_id.id,
                'implementation': 'no_gap',
                'use_date_range': True,
            }])
            suffix = sequence.next_by_id()

        return f'{prefix}{vat}000{year}{int(suffix):0{8}X}'

    def _l10n_co_dian_get_last_accepted_document(self):
        self.ensure_one()
        return next(
            (d for d in self.l10n_co_dian_document_ids.sorted() if d.state == 'invoice_accepted'),
            self.env['l10n_co_dian.document'],
        )

    def _l10n_co_dian_cron_update_event_status(self, *, limit=3):
        date_limit = fields.Datetime.now().date() - timedelta(days=30)

        # There is no clear-cut way to distinguish processed and non-processed moves
        # so we need an extra field to prevent multiple batches from processing the same record
        to_process_domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('l10n_co_dian_commercial_state', 'in', ('pending', 'received', 'goods_received')),
            ('l10n_co_edi_cufe_cude_ref', '!=', False),
            ('invoice_date', '>=', date_limit),
            ('l10n_co_dian_processed_by_get_event_status_cron', '=', False),
        ]

        records = self.search(domain=to_process_domain, limit=limit)
        records.l10n_co_dian_action_update_event_status()
        records.l10n_co_dian_processed_by_get_event_status_cron = True

        remaining = self.search_count(domain=to_process_domain)
        if not remaining:
            # reset processed by cron field
            processed_records = self.search([('l10n_co_dian_processed_by_get_event_status_cron', '=', True)])
            processed_records.l10n_co_dian_processed_by_get_event_status_cron = False

        self.env['ir.cron']._commit_progress(len(records), remaining=remaining)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _l10n_co_dian_net_price_subtotal(self):
        """ Returns the price subtotal after discount in company currency. """
        self.ensure_one()
        return self.move_id.direction_sign * self.balance

    def _l10n_co_dian_gross_price_subtotal(self):
        """ Returns the price subtotal without discount in company currency. """
        self.ensure_one()
        if self.discount == 100.0:
            return 0.0
        else:
            net_price_subtotal = self._l10n_co_dian_net_price_subtotal()
            return self.company_id.currency_id.round(net_price_subtotal / (1.0 - (self.discount or 0.0) / 100.0))
