# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
import time
import uuid

from werkzeug.urls import url_quote
from markupsafe import Markup

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import get_lang, is_html_empty, format_date
from odoo.tools.urls import urljoin as url_join


class SignRequest(models.Model):
    _name = 'sign.request'
    _description = "Signature Request"
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _get_mail_link(self, email, subject):
        return "mailto:%s?subject=%s" % (url_quote(email), url_quote(subject))

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name)
                for model in self.env['ir.model'].sudo().search([('model', '!=', 'sign.request'), ('is_mail_thread', '=', 'True')])]

    template_id = fields.Many2one('sign.template', string="Template", required=True, index=True)
    subject = fields.Char(string="Email Subject")
    reference = fields.Char(required=True, string="Document Name", help="This is how the document will be named in the mail")
    reference_doc = fields.Reference(string="Linked To", selection='_selection_target_model', index='btree_not_null')

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True, copy=False)
    share_link = fields.Char(string="Share Link", compute='_compute_share_link', readonly=False)
    is_shared = fields.Boolean(string="Share Request Button", compute='_compute_is_shared', inverse='_inverse_is_shared')

    request_item_ids = fields.One2many('sign.request.item', 'sign_request_id', string="Signers", copy=True)
    state = fields.Selection([
        ("shared", "Shared"),
        ("sent", "To Sign"),
        ("signed", "Signed"),
        ("canceled", "Cancelled"),
        ("expired", "Expired"),
    ], default='sent', tracking=True, group_expand=True, copy=False, index=True)

    template_document_ids = fields.Many2many('sign.document', string="Documents", compute='_compute_template_document_ids')
    completed_document_ids = fields.One2many('sign.completed.document', 'sign_request_id', string="Completed Documents Binaries", copy=False)
    nb_wait = fields.Integer(string="Sent Requests", compute="_compute_stats", store=True)
    nb_closed = fields.Integer(string="Completed Signatures", compute="_compute_stats", store=True)
    nb_total = fields.Integer(string="Requested Signatures", compute="_compute_stats", store=True)
    progress = fields.Char(string="Progress", compute="_compute_progress", compute_sudo=True)
    start_sign = fields.Boolean(string="Signature Started", help="At least one signer has signed the document.", compute="_compute_progress", compute_sudo=True)
    integrity = fields.Boolean(string="Integrity of the Sign request", compute='_compute_hashes', compute_sudo=True)

    active = fields.Boolean(default=True, string="Active", copy=False)
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    color = fields.Integer()
    request_item_infos = fields.Binary(compute="_compute_request_item_infos")
    last_action_date = fields.Datetime(related="message_ids.create_date", readonly=True, string="Last Action Date")
    completion_date = fields.Date(string="Completion Date", compute="_compute_completion_date", compute_sudo=True, store=True)
    communication_company_id = fields.Many2one('res.company', string="Company used for communication", default=lambda self: self.env.company)

    sign_log_ids = fields.One2many('sign.log', 'sign_request_id', string="Logs", help="Activity logs linked to this request")
    template_tags = fields.Many2many('sign.template.tag', string='Tags')
    cc_partner_ids = fields.Many2many('res.partner', string='Copy to', compute='_compute_cc_partners')
    message = fields.Html('sign.message')
    message_cc = fields.Html('sign.message_cc')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', readonly=True, copy=False, ondelete="restrict", bypass_search_access=True)
    completed_document_attachment_ids = fields.Many2many('ir.attachment', 'sign_request_completed_document_rel', string='Completed Documents', readonly=True, copy=False, ondelete="restrict", bypass_search_access=True)

    need_my_signature = fields.Boolean(compute='_compute_need_my_signature', search='_search_need_my_signature')

    validity = fields.Date(string='Valid Until')
    reminder_enabled = fields.Boolean(default=False)
    reminder = fields.Integer(string='Reminder', default=7)
    last_reminder = fields.Date(string='Last reminder', default=lambda self: fields.Date.today())
    certificate_reference = fields.Boolean(string="Certificate Reference", default=False)

    send_channel = fields.Selection([
        ("email", "Email"),
    ], string="Delivery Method", default='email', required=True)

    @api.depends('template_id')
    def _compute_template_document_ids(self):
        for sign_request in self:
            sign_request.template_document_ids = sign_request.template_id.sudo().document_ids

    @api.constrains('reminder_enabled', 'reminder')
    def _check_reminder(self):
        for request in self:
            if request.reminder_enabled and request.reminder <= 0:
                raise UserError(_("We can only send reminders in the future - as soon as we find a way to send reminders in the past we'll notify you.\nIn the mean time, please make sure to input a positive number of days for the reminder interval."))

    @api.depends('state')
    def _compute_is_shared(self):
        for sign_request in self:
            sign_request.is_shared = sign_request.state == 'shared'

    def _inverse_is_shared(self):
        for sign_request in self:
            if sign_request.is_shared:
                sign_request.state = 'shared'
            else:
                sign_request.state = 'sent'

    @api.depends_context('uid')
    def _compute_need_my_signature(self):
        my_partner_id = self.env.user.partner_id
        for sign_request in self:
            sign_request.need_my_signature = any(sri.partner_id.id == my_partner_id.id and sri.state == 'sent' and sri.is_mail_sent for sri in sign_request.request_item_ids)

    @api.model
    def _search_need_my_signature(self, operator, value):
        if operator != 'in':
            return NotImplemented
        my_partner_id = self.env.user.partner_id
        documents_ids = self.env['sign.request.item'].search([('partner_id', '=', my_partner_id.id), ('state', '=', 'sent'), ('is_mail_sent', '=', True)]).mapped('sign_request_id').ids
        return [('id', 'not in', documents_ids)]

    @api.depends('request_item_ids.state')
    def _compute_stats(self):
        for rec in self:
            rec.nb_total = len(rec.request_item_ids)
            rec.nb_wait = len(rec.request_item_ids.filtered(lambda sri: sri.state == 'sent'))
            rec.nb_closed = rec.nb_total - rec.nb_wait

    @api.depends('request_item_ids.state')
    def _compute_progress(self):
        for rec in self:
            rec.start_sign = bool(rec.nb_closed)
            rec.progress = "{} / {}".format(rec.nb_closed, rec.nb_total)

    @api.depends('request_item_ids.state')
    def _compute_completion_date(self):
        for rec in self:
            rec.completion_date = rec.request_item_ids.sorted(key="signing_date", reverse=True)[:1].signing_date if not rec.nb_wait else None

    @api.depends('request_item_ids.state', 'request_item_ids.partner_id.name')
    def _compute_request_item_infos(self):
        for request in self:
            request.request_item_infos = [{
                'id': item.id,
                'partner_name': item.display_name,
                'state': item.state,
                'signing_date': item.signing_date or ''
            } for item in request.request_item_ids]

    @api.depends('message_follower_ids.partner_id')
    def _compute_cc_partners(self):
        for sign_request in self:
            sign_request.cc_partner_ids = sign_request.message_follower_ids.partner_id - sign_request.request_item_ids.partner_id

    @api.depends('request_item_ids.access_token', 'state')
    def _compute_share_link(self):
        self.share_link = False
        for sign_request in self.filtered(lambda sr: sr.state == 'shared'):
            sign_request.share_link = "%s/sign/document/mail/%s/%s" % (self.get_base_url(), sign_request.id, sign_request.request_item_ids[0].sudo().access_token)

    @api.model_create_multi
    def create(self, vals_list):
        sign_requests = super().create(vals_list)
        sign_requests.template_id._check_send_ready()
        for sign_request in sign_requests:
            if not sign_request.request_item_ids:
                raise ValidationError(_("A valid sign request needs at least one sign request item"))
            sign_request.template_tags = [Command.set(sign_request.template_id.tag_ids.ids)]
            sign_request.attachment_ids.write({'res_model': sign_request._name, 'res_id': sign_request.id})
            sign_request.message_subscribe(partner_ids=sign_request.request_item_ids.partner_id.ids)
            sign_request._populate_constant_items()
            self.env['sign.log'].sudo().create({'sign_request_id': sign_request.id, 'action': 'create'})

        if not self.env.context.get('no_sign_mail'):
            sign_requests.send_signature_accesses()
        return sign_requests

    def _populate_constant_items(self):
        self.ensure_one()
        sign_values_by_role = defaultdict(
            lambda: defaultdict(lambda: self.env['sign.item']))
        for item in self.template_id.sign_item_ids:
            if item.constant:
                sign_values_by_role[item.responsible_id][str(item.id)] = {
                    # For constant strikethrough items, use "striked" instead of item name,
                    # since item name returns "strikethrough" but we need "striked" to set the value correctly.
                    "name": item.name if item.type_id.item_type != 'strikethrough' else 'striked',
                    "type_id": item.type_id.id,
                    "auto_field": item.type_id.sudo().auto_field
                }

        if not sign_values_by_role:
            return

        for sign_request_item in self.sudo().request_item_ids:
            if sign_request_item.role_id in sign_values_by_role:
                sign_items = sign_values_by_role[sign_request_item.role_id]
                corrected_dict = sign_items.copy()
                for key, value in sign_items.items():
                    corrected_dict[key] = value["name"]
                    if value.get("auto_field"):
                        corrected_dict[key] = sign_request_item._get_auto_field_value({
                            "id": value.get("type_id"),
                            "auto_field": value.get("auto_field")
                        })

                sign_request_item._fill(corrected_dict)

    def write(self, vals):
        today = fields.Date.today()
        if vals.get('validity') and fields.Date.from_string(vals['validity']) < today:
            vals['state'] = 'expired'

        res = super().write(vals)
        return res

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'attachment_ids' not in default:
            for request, vals in zip(self, vals_list):
                vals['attachment_ids'] = request.attachment_ids.copy().ids
        return vals_list

    def copy(self, default=None):
        sign_requests = super().copy(default)
        for old_request, new_request in zip(self, sign_requests):
            new_request.message_subscribe(partner_ids=old_request.cc_partner_ids.ids)
        return sign_requests

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_signed(self):
        """
        Raise an error if any of the records are in 'signed' state.
        """
        if any(r.state == 'signed' for r in self):
            raise UserError(_("Signed documents cannot be deleted for legal reasons. Please archive them instead."))

    def action_archive(self):
        self.filtered(lambda sr: sr.active and sr.state == 'sent').cancel()
        return super().action_archive()

    def _check_senders_validity(self):
        invalid_senders = self.create_uid.filtered(lambda u: not u.email_formatted)
        if invalid_senders:
            raise ValidationError(_("Please configure senders'(%s) email addresses", ', '.join(invalid_senders.mapped('name'))))

    def _check_signers_roles_validity(self):
        for sign_request in self:
            template_roles = sign_request.sudo().template_id.sign_item_ids.responsible_id
            sign_request_items = sign_request.request_item_ids
            if len(sign_request_items) != max(len(template_roles), 1) or \
                    set(sign_request_items.role_id.ids) != (set(template_roles.ids) if template_roles else set([self.env.ref('sign.sign_item_role_default').id])):
                raise ValidationError(_("You must specify one signer for each role of your sign template"))

    def _check_signers_partners_validity(self):
        for sign_request in self:
            sign_request_items = sign_request.request_item_ids
            if sign_request.state != 'shared' and any(not sri.partner_id for sri in sign_request_items):
                raise ValidationError(_("A non-shared sign request's should not have any signer with an empty partner"))

    def _get_final_recipients(self):
        all_recipients = set(self.request_item_ids.mapped('signer_email')) | \
                         set(self.cc_partner_ids.filtered(lambda p: p.email_formatted).mapped('email'))
        return all_recipients

    def _get_next_sign_request_items(self):
        self.ensure_one()
        sign_request_items_sent = self.request_item_ids.filtered(lambda sri: sri.state == 'sent')
        if not sign_request_items_sent:
            return self.env['sign.request.item']
        smallest_order = min(sign_request_items_sent.mapped('mail_sent_order'))
        next_request_items = sign_request_items_sent.filtered(lambda sri: sri.mail_sent_order == smallest_order)
        return next_request_items

    def go_to_document(self):
        self.ensure_one()
        request_items = self.request_item_ids.filtered(lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id.id == self.env.user.partner_id.id))
        sequenced_signature_mail = any(req.mail_sent_order > 1 for req in self.request_item_ids)
        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.Document',
            'context': {
                'id': self.id,
                'token': self.access_token,
                'need_to_sign': bool(request_items),
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': {str(item.id): item.is_mail_sent for item in self.request_item_ids},
                'sequenced_signature_mail': sequenced_signature_mail,
            },
        }

    def go_to_signable_document(self, request_items=None):
        """ go to the signable document as the signers for specified request_items or the current user"""
        self.ensure_one()
        if not request_items:
            request_items = self.request_item_ids.filtered(lambda r: not r.partner_id or (r.state == 'sent' and r.partner_id.id == self.env.user.partner_id.id))
        if not request_items:
            return
        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.SignableDocument',
            'context': {
                'id': self.id,
                'token': request_items[:1].sudo().access_token,
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': {item.id: item.is_mail_sent for item in self.request_item_ids},
                'template_editable': self.nb_closed == 0,
                'token_list': request_items[1:].sudo().mapped('access_token'),
                'name_list': [item.partner_id.name for item in request_items[1:]],
            },
        }

    def get_sign_request_documents(self):
        if not self:
            raise UserError(_('You should select at least one document to download.'))

        if len(self) == 1:
            if self.state == 'signed':
                return {
                    'name': 'Signed Document',
                    'type': 'ir.actions.act_url',
                    'url': '/sign/download/%(request_id)s/%(access_token)s/completed' % {'request_id': self.id, 'access_token': self.access_token},
                }
            else:
                return {
                    'name': 'Template Document',
                    'type': 'ir.actions.act_url',
                    'url': '/sign/download/%(request_id)s/%(access_token)s/origin' % {'request_id': self.id, 'access_token': self.access_token},
                }
        else:
            return {
                'name': 'Sign Request Documents',
                'type': 'ir.actions.act_url',
                'url': f'/sign/download/zip/{",".join(map(str, self.ids))}',
            }

    def _get_linked_record_action(self, default_action=None):
        """" Return the default action for any kind of record. This method can be override for specific kind or rec
        """
        self.ensure_one()
        if not default_action:
            default_action = {}
        # user might not have access to Action Window model
        action_rec_sudo = self.env['ir.actions.act_window'].sudo().sudo().search([
            ('res_model', '=', self.reference_doc._name),
            ('context', 'not ilike', 'active_id')], limit=1)
        if action_rec_sudo:
            action = action_rec_sudo._get_action_dict()
            action.update({
                "views": [(False, "form")],
                "view_mode":  'form',
                "res_id": self.reference_doc.id,
                "target": 'current',
            })
        else:
            action = default_action
        return action

    def get_close_values(self):
        self.ensure_one()
        # check if frontend user or backend
        action = self.env["ir.actions.actions"]._for_xml_id("sign.sign_request_action")
        result = {"action": action, "label": _("Close"), "custom_action": False}
        if self.reference_doc and self.reference_doc.exists():
            action = self._get_linked_record_action(action)
            result = {"action": action, "label": _("Back to %s", self.reference_doc._description), "custom_action": True}
        return result

    @api.onchange("progress", "start_sign")
    def _compute_hashes(self):
        for document in self:
            try:
                document.integrity = self.sign_log_ids._check_document_integrity()
            except Exception:
                document.integrity = False

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self.favorited_ids else 4, self.env.user.id)]})

    def _refuse(self, refuser, refusal_reason):
        """ Refuse a SignRequest. It can only be used in SignRequestItem._refuse
        :param res.partner refuser: the refuser who refuse to sign
        :param str refusal_reason: the refusal reason provided by the refuser
        """
        self.ensure_one()
        if self.state != 'sent':
            raise UserError(_("This sign request cannot be refused"))
        self._check_senders_validity()
        self.cancel()

        # cancel request and activities for other unsigned users
        for user in self.request_item_ids.partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_user')):
            self.activity_unlink(['sign.mail_activity_data_signature_request'], user_id=user.id)

        # send emails to signers and cc_partners
        for sign_request_item in self.request_item_ids:
            self._send_refused_message(refuser, refusal_reason, sign_request_item.partner_id,
                                       access_token=sign_request_item.sudo().access_token, force_send=True, sign_request_item=sign_request_item)
        for partner in self.cc_partner_ids.filtered(lambda p: p.email_formatted) - self.request_item_ids.partner_id:
            self._send_refused_message(refuser, refusal_reason, partner)

    def _send_refused_message(self, refuser, refusal_reason, partner, access_token=None, force_send=False, sign_request_item=None):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        subject = _("The document %(template_name)s has been rejected by %(partner_name)s",
            template_name=self.template_id.name,
            partner_name=partner.name,
        )
        base_url = self.get_base_url()
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        body = self.env['ir.qweb']._render('sign.sign_template_mail_refused', {
            'record': self,
            'recipient': partner,
            'refuser': refuser,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': subject,
            'body': Markup('<p style="white-space: pre">{}</p>').format(refusal_reason),
        }, lang=partner_lang, minimal_qcontext=True)

        self.with_context(lang=partner.lang or self.env.lang)._message_send_mail(
            body,
            record_name=self.reference,
            notif_values={
                'model_description': _('Signature'),
                'company': self.communication_company_id or self.create_uid.company_id,
                'partner': partner,
            },
            mail_values={
                'subject': subject,
            },
            force_send=force_send,
        )

    def send_signature_accesses(self):
        # Send/Resend accesses for 'sent' sign.request.items by email
        allowed_request_ids = self.filtered(lambda sr: sr.state == 'sent')
        allowed_request_ids._check_senders_validity()
        for sign_request in allowed_request_ids:
            sign_request._get_next_sign_request_items().send_signature_accesses()
            sign_request.last_reminder = fields.Date.today()

    @api.model
    def _cron_reminder(self):
        today = fields.Date.today()
        # find all expired sign requests and those that need a reminder
        # in one query, the code will handle them differently
        # note: archived requests are not fetched.
        self.flush_model()
        self.env.cr.execute(f'''
        SELECT id
        FROM sign_request sr
        WHERE sr.state = 'sent'
        AND active = TRUE
        AND (
            sr.validity < '{today}'
            OR (sr.reminder_enabled AND sr.last_reminder + sr.reminder * ('1 day'::interval) <= '{today}')
        )
        ''')
        res = self.env.cr.fetchall()
        request_to_send = self.env['sign.request']
        for request in self.browse(v[0] for v in res):
            if request.validity and request.validity < today:
                request.state = 'expired'
            else:
                request_to_send += request
        request_to_send.with_context(force_send=False).send_signature_accesses()

    def _sign(self):
        """ Sign a SignRequest. It can only be used in the SignRequestItem._sign """
        self.ensure_one()
        if self.state != 'sent' or any(sri.state != 'completed' for sri in self.request_item_ids):
            raise UserError(_("This sign request cannot be signed"))
        self.write({'state': 'signed'})
        self._send_completed_documents()

        if self.reference_doc:
            model = self.env['ir.model']._get(self.reference_doc._name)
            if model.is_mail_thread:
                self.reference_doc.message_post_with_source(
                    "sign.message_signature_link",
                    render_values={"request": self, "salesman": self.env.user.partner_id},
                    subtype_xmlid='mail.mt_note',
                )
                # attach a copy of the signed document to the record for easy retrieval
                attachment_values = []
                for doc in self.completed_document_ids:
                    attachment_values.append({
                        "name": doc.document_id.name,
                        "datas": doc.file,
                        "type": "binary",
                        "res_model": self.reference_doc._name,
                        "res_id": self.reference_doc.id
                    })
                self.env["ir.attachment"].create(attachment_values)

    def cancel(self):
        for sign_request in self:
            sign_request.write({'access_token': self._default_access_token(), 'state': 'canceled'})
        self.request_item_ids._cancel()

        # cancel activities for signers
        for user in self.request_item_ids.sudo().partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_user')):
            self.activity_unlink(['sign.mail_activity_data_signature_request'], user_id=user.id)

        self.env['sign.log'].sudo().create([{'sign_request_id': sign_request.id, 'action': 'cancel'} for sign_request in self])

    def _send_completed_documents(self):
        """ Send the completed document to signers and Contacts in copy with emails
        """
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_('The sign request has not been fully signed'))
        self._check_senders_validity()

        if not self.completed_document_ids:
            self._generate_completed_documents()

        signers = [{'name': signer.partner_id.name, 'email': signer.signer_email, 'id': signer.partner_id.id} for signer in self.request_item_ids]
        request_edited = any(log.action == "update" for log in self.sign_log_ids)
        for sign_request_item in self.request_item_ids:
            self._send_completed_documents_message(signers, request_edited, sign_request_item.partner_id,
                                                   access_token=sign_request_item.sudo().access_token, with_message_cc=False, force_send=True, sign_request_item=sign_request_item)

        cc_partners_valid = self.cc_partner_ids.filtered(lambda p: p.email_formatted)
        for cc_partner in cc_partners_valid:
            self._send_completed_documents_message(signers, request_edited, cc_partner)
        if cc_partners_valid:
            body = _(
                "The mail has been sent to contacts in copy: %(contacts)s",
                contacts=cc_partners_valid.mapped("name"),
            )
            if not is_html_empty(self.message_cc):
                body += self.message_cc
            self.message_post(body=body, attachment_ids=self.attachment_ids.ids + self.completed_document_attachment_ids.ids)
        if self.reference_doc:
            record_body = _("The document %s has been fully signed.", self._get_html_link())
            self.reference_doc.message_post(
                body=record_body,
                attachment_ids=self.completed_document_attachment_ids.ids,
                partner_ids=cc_partners_valid.ids,
            )

    def _send_completed_documents_message(self, signers, request_edited, partner, access_token=None, with_message_cc=True, force_send=False, sign_request_item=None):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        base_url = self.get_base_url()
        body = self.env['ir.qweb']._render('sign.sign_template_mail_completed', {
            'record': self,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': '%s signed' % self.reference,
            'body': self.message_cc if with_message_cc and not is_html_empty(self.message_cc) else False,
            'recipient_name': partner.name,
            'recipient_id': partner.id,
            'signers': signers,
            'request_edited': request_edited,
            }, lang=partner_lang, minimal_qcontext=True)

        self.with_context(lang=partner.lang or self.env.lang)._message_send_mail(
            body,
            record_name=self.reference,
            notif_values={
                'model_description': _('Signature'),
                'company': self.communication_company_id or self.create_uid.company_id,
                'partner': partner,
            },
            mail_values={
                'attachment_ids': self.attachment_ids.ids + self.completed_document_attachment_ids.ids,
                'subject': _('%s has been edited and signed', self.reference) if request_edited else _('%s has been signed', self.reference),
            },
            force_send=force_send,
        )

    @api.autovacuum
    def _gc_expired_sr(self):
        """
        Deletes all the shared sign requests which have an expired validity date
        """
        sign_request = self.env["sign.request"].search([("state", "=", "shared"), ("validity", "<", fields.Date.today())])
        sign_request.unlink()

    ##################
    # PDF Rendering  #
    ##################

    def _get_user_formatted_datetime(self, datetime_val):
        """
        Get the user's preferred datetime format based on their language settings.
        """
        lang = self.env['res.lang']._lang_get(self.create_uid.lang)
        user_date_format, user_time_format = lang.date_format, lang.time_format
        return datetime_val.strftime(f"{user_date_format} {user_time_format}")

    def _get_final_signature_log_hash(self):
        """
        Fetch the log_hash of the final signature from the sign.log table.
        """
        self.ensure_one()
        if not self.certificate_reference:
            return False

        final_log = self.env['sign.log'].search([
            ('sign_request_id', '=', self.id),
            ('action', 'in', ['sign', 'create']),
        ], order='id DESC', limit=1)

        return final_log.log_hash if final_log else False

    def _generate_completed_documents(self):
        if self.state != 'signed':
            raise UserError(_("The completed document cannot be created because the sign request is not fully signed"))

        for record in self:
            if not record.completed_document_ids:
                self.env['sign.completed.document'].create([{
                    'sign_request_id': record.id,
                    'document_id': document.id,
                } for document in record.template_id.document_ids])
                record.completed_document_ids._generate_completed_document()
                attachment_ids = self.env['ir.attachment'].create([{
                    'name': document.document_id.name,
                    'datas': document.file,
                    'type': 'binary',
                    'res_model': self._name,
                    'res_id': record.id,
                } for document in record.completed_document_ids])

                # print the report with the public user in a sudoed env
                # public user because we don't want groups to pollute the result
                # (e.g. if the current user has the group Sign Manager,
                # some private information will be sent to *all* signers)
                # sudoed env because we have checked access higher up the stack
                public_user = self.env.ref('base.public_user', raise_if_not_found=False)
                if not public_user:
                    # public user was deleted, fallback to avoid crash (info may leak)
                    public_user = self.env.user
                pdf_content, __ = self.env["ir.actions.report"].with_user(public_user).sudo()._render_qweb_pdf(
                    'sign.action_sign_request_print_logs',
                    record.id,
                    data={'format_date': format_date, 'company_id': record.communication_company_id}
                )
                attachment_log = self.env['ir.attachment'].create({
                    'name': self.env._("Certificate of completion - %s.pdf", time.strftime('%Y-%m-%d - %H:%M:%S')),
                    'raw': pdf_content,
                    'type': 'binary',
                    'res_model': self._name,
                    'res_id': record.id,
                })
                self.completed_document_attachment_ids = [Command.link(attachment_log.id)] + [Command.link(att.id) for att in attachment_ids]

    def _get_signing_field_name(self) -> str:
        """Generates a name for the signing field of the pdf document

        Returns:
            str: the name of the signature field
        """
        return self.env.company.name

    ##################
    # Mail overrides #
    ##################

    def _message_send_mail(self, body, notif_values=None, mail_values=None, record_name=False, force_send=False):
        """ Shortcut to sent a notification or an email. """
        notif_values = notif_values or {}
        company = notif_values.get('company')
        model_description = notif_values.get('model_description')
        partner = notif_values.get('partner')
        notification_layout_xmlid = notif_values.get('notification_layout_xmlid', 'sign.sign_mail_notification_light')
        scheduled_date = self.env.context.get('scheduled_date', False)

        mail_values = mail_values or {}
        if 'author_id' not in mail_values:
            mail_values['author_id'] = self.create_uid.partner_id.id
            mail_values['email_from'] = self.create_uid.email_formatted
        if 'email_to' not in mail_values:
            mail_values['email_to'] = partner.email_formatted

        if partner and len(partner.user_ids) == 1 and partner.user_ids.notification_type == "inbox":
            return self.message_notify(
                attachment_ids=mail_values.get("attachment_ids"),
                author_id=self.create_uid.partner_id.id,
                body=body,
                email_from=mail_values.get("email_from"),
                force_record_name=record_name,
                force_send=force_send,
                mail_auto_delete=False,
                model_description=model_description,
                partner_ids=partner.ids,
                subject=mail_values.get("subject"),
            )

        mail_values['body_html'] = self.env['mail.render.mixin']._render_encapsulate(
            notification_layout_xmlid, body,
            context_record=self,
            add_context={
                'company': company,
                'model_description': model_description,
                'record_name': record_name,
            },
        )
        mail_values['reply_to'] = mail_values.get('email_from')
        if scheduled_date:
            mail_values['scheduled_date'] = scheduled_date
        mail = self.env['mail.mail'].sudo().create(mail_values)
        if force_send and not scheduled_date:
            mail.send_after_commit()
        return mail

    def _schedule_activity(self, sign_users):
        for user in sign_users:
            self.with_context(mail_activity_quick_update=True).activity_schedule(
                'sign.mail_activity_data_signature_request',
                user_id=user.id
            )
