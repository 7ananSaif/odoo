# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, Command
from odoo.exceptions import UserError
from odoo.tools import format_date


class SignSendRequest(models.TransientModel):
    _name = 'sign.send.request'
    _description = 'Sign send request'

    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search(
            [
                ('model', '!=', 'sign.request'),
                ('is_mail_thread', '=', 'True'),
            ]
        )]

    activity_id = fields.Many2one('mail.activity', 'Linked Activity', readonly=True)
    reference_doc = fields.Reference(string="Linked to", selection='_selection_target_model', readonly=True)
    has_default_template = fields.Boolean()
    available_template_ids = fields.Many2many(comodel_name='sign.template', compute='_compute_available_template_ids')
    template_id = fields.Many2one('sign.template', string="Sign Template", ondelete='cascade')

    signer_ids = fields.One2many('sign.send.request.signer', 'sign_send_request_id', string="Signers", compute='_compute_signer_ids', store=True)
    set_sign_order = fields.Boolean(string="Signing Order",
                                    help="""Specify the order for each signer. The signature request only gets sent to \
                                    the next signers in the sequence when all signers from the previous level have \
                                    signed the document.
                                    """)
    signer_id = fields.Many2one('res.partner', string="Send To")
    signers_count = fields.Integer(compute='_compute_signers_count')
    cc_partner_ids = fields.Many2many('res.partner', string="Copy to", help="Contacts in copy will be notified by email once the document is either fully signed or refused.")
    is_user_signer = fields.Boolean(compute='_compute_is_user_signer')

    subject = fields.Char(string="Subject", compute='_compute_subject', store=True, readonly=False)
    body = fields.Html('body', compute='_compute_mail_message_body', readonly=False, help="Message to be sent to signers of the specified document", store=True)
    message_cc = fields.Html("CC Message", help="Message to be sent to contacts in copy of the signed document")
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', bypass_search_access=True)
    filename = fields.Char("Filename", compute='_compute_filename', store=True)

    validity = fields.Date(compute='_compute_validity', store=True, readonly=False,
                           string='Valid Until', help="Leave empty for requests without expiration.")
    reminder_enabled = fields.Boolean(default=False)
    reminder = fields.Integer(string='Reminder', default=7)
    certificate_reference = fields.Boolean(string="Certificate Reference", default=False, help="If checked, the unique certificate reference will be added on the final signed document.")
    model = fields.Char('Related Document Model')
    res_ids = fields.Text('Related Document IDs')
    scheduled_date = fields.Char('Scheduled Date')

    only_autofill_readonly = fields.Boolean(
        string='Only Autofill',
        compute='_compute_only_autofill_readonly',
    )
    display_download_button = fields.Boolean(
        string="Display Download Button",
        compute='_compute_display_download_button',
        store=False
    )

    @api.constrains('validity')
    def _check_validity(self):
        if self.validity and self.validity < fields.Date.today():
            raise UserError(self.env._('Request expiration date must be set in the future.'))

    @api.onchange('reminder')
    def _onchange_reminder(self):
        if self.reminder > 365:
            self.reminder = 365

    def _get_default_signer(self):
        """Helper method to define default signer (see hr_recruitment_sign/wizard/sign_send_request.py).
        """
        if self.reference_doc or self.env.context.get('default_reference_doc'):
            ref = self.reference_doc
            # If the reference document has a direct partner, such as in the contacts module.
            if ref._name == 'res.partner':
                return ref.id

            # return the partner_id of the reference document
            partner = 'partner_id' in ref and ref.partner_id
            if partner:
                return partner.id

            # If the reference document has an user_id, some modules like MRP etc.
            user = 'user_id' in ref and ref.user_id
            if user and user.partner_id:
                return user.partner_id.id

            # If the reference document has an employee_id, some modules like hr_recruitment, expense, etc.
            employee = 'employee_id' in ref and ref.employee_id
            if employee and employee.work_contact_id:
                return employee.work_contact_id.id

        return self.env.context.get("default_signer_id", self.env.user.partner_id.id)

    @api.depends('template_id', 'set_sign_order', 'template_id.sign_item_ids')
    def _compute_signer_ids(self):
        default_signer = self._get_default_signer()
        for wiz in self:
            template = wiz.template_id
            roles = template.sign_item_ids.responsible_id.sorted()
            signer_ids = []
            if (self.signer_ids and len(self.signer_ids) == len(roles)):
                # Check if all signers currently have the default mail_sent_order = 1
                all_default = all(signer.mail_sent_order == 1 for signer in self.signer_ids)
                for default_signing_order, signer in enumerate(self.signer_ids):
                    if wiz.set_sign_order:
                        # If signing order is enabled, assign based on order only if all signers are default.
                        # Otherwise, keep their existing mail_sent_order.
                        mail_sent_order = default_signing_order + 1 if all_default else signer.mail_sent_order
                    else:
                        mail_sent_order = 1
                    signer_ids.append((
                        0, 0, {
                            'role_id': signer.role_id.id,
                            'partner_id': signer.partner_id.id,
                            'mail_sent_order': mail_sent_order,
                        }
                    ))
            else:
                for default_signing_order, role in enumerate(roles):
                    # First signer logic
                    if default_signing_order == 0:
                        # If role has assign_to, use it; else use default_signer
                        partner_id = role.assign_to.id if role.assign_to else default_signer
                    else:
                        # For other roles, check assign_to
                        partner_id = role.assign_to.id if role.assign_to else False
                    signer_vals = {
                        'role_id': role.id,
                        'partner_id': partner_id,
                        'mail_sent_order': default_signing_order + 1 if wiz.set_sign_order else 1,
                    }
                    signer_ids.append((0, 0, signer_vals))
            wiz.signer_ids = [(5, 0, 0)] + signer_ids

    @api.depends('signer_ids')
    def _compute_signers_count(self):
        for wiz in self:
            wiz.signers_count = len(wiz.signer_ids)

    @api.depends('template_id', 'reference_doc')
    def _compute_display_name(self):
        for wiz in self:
            display_name = self.env._("Sign Request ")
            if wiz.reference_doc:
                display_name = self.env._("Sign Request - %s", wiz.reference_doc.display_name)
            wiz.display_name = display_name

    @api.depends('template_id', 'reference_doc')
    def _compute_subject(self):
        for wiz in self:
            subject = self.env._("Signature Request")
            if wiz.reference_doc:
                subject = self.env._("Signature Request - %(template_name)s - %(res_name)s", template_name=wiz.template_id.display_name, res_name=wiz.reference_doc.display_name or '')
            elif wiz.template_id:
                subject = self.env._("Signature Request - %(file_name)s", file_name=wiz.template_id.name)
            wiz.subject = subject

    @api.depends('template_id', 'reference_doc')
    def _compute_filename(self):
        for wiz in self:
            filename = self.env._("Sign Request")
            if wiz.reference_doc:
                filename = self.env._("Sign Request - %s", wiz.reference_doc.display_name)
            elif wiz.template_id:
                filename = wiz.template_id.display_name
            wiz.filename = filename

    @api.depends('template_id')
    def _compute_validity(self):
        for wiz in self:
            if wiz.template_id:
                if wiz.template_id.signature_request_validity:
                    wiz.validity = fields.Date.today() + relativedelta(days=wiz.template_id.signature_request_validity)
                else:
                    wiz.validity = None

    @api.depends('signer_ids.partner_id', 'signer_id', 'signers_count')
    def _compute_is_user_signer(self):
        if self.signers_count and self.env.user.partner_id in self.signer_ids.mapped('partner_id'):
            self.is_user_signer = True
        elif not self.signers_count and self.env.user.partner_id == self.signer_id:
            self.is_user_signer = True
        else:
            self.is_user_signer = False

    @api.depends('reference_doc')
    def _compute_available_template_ids(self):
        non_specific_templates = self.env['sign.template'].search([('model_id', '=', False)])._filtered_access('read')
        template_by_model = {}
        if self.reference_doc:
            model_names = [ref._name for ref in self.reference_doc if self.reference_doc]
            # unprivilegied user don't have access to ir.model
            model_ids = self.env['ir.model'].sudo().search([('model', 'in', model_names)]).ids
            res = self.env['sign.template']._read_group(
                [('model_id', 'in', model_ids)],
                groupby=['model_id'],
                aggregates=['id:recordset'],
            )
            for model, template in res:
                template_by_model[model.id] = template
        for wiz in self:
            all_template_ids = non_specific_templates.ids
            if wiz.reference_doc:
                model = self.env['ir.model'].sudo()._get(wiz.reference_doc._name)
                other_templates = template_by_model.get(model.id, self.env['sign.template'])
                all_template_ids += other_templates.ids
            wiz.available_template_ids = [Command.set(all_template_ids)]

    @api.depends('template_id')
    def _compute_mail_message_body(self):
        for wiz in self:
            # Compute mail message
            if wiz.template_id:
                wiz.body = wiz.template_id.message

    # ==== Business methods ====

    def _activity_done(self):
        signatories = self.signer_id.name or self.signer_ids.partner_id.mapped('name')
        feedback = self.env._('Signature requested for template: %(template)s\nSignatories: %(signatories)s', template=self.template_id.name, signatories=signatories)
        self.activity_id._action_done(feedback=feedback)

    def create_request(self):
        send_channel = self.env.context.get('send_channel', 'email')
        template_id = self.template_id.id
        if self.signers_count:
            signers = [{'partner_id': signer.partner_id.id, 'role_id': signer.role_id.id, 'mail_sent_order': signer.mail_sent_order} for signer in self.signer_ids]
        else:
            signers = [{'partner_id': self.signer_id.id, 'role_id': self.env.ref('sign.sign_item_role_default').id, 'mail_sent_order': self.signer_ids.mail_sent_order}]
        cc_partner_ids = self.cc_partner_ids.ids
        reference = self.filename or self.template_id.name
        subject = self.subject
        message = self.body
        message_cc = self.message_cc
        attachment_ids = self.attachment_ids
        scheduled_date = self.scheduled_date or False
        reference_doc = None
        if self.reference_doc:
            reference_doc = f"{self.reference_doc._name},{self.reference_doc.id}"
        sign_request = self.env['sign.request'].with_context(scheduled_date=scheduled_date).create({
            'template_id': template_id,
            'request_item_ids': [Command.create({
                'partner_id': signer['partner_id'],
                'role_id': signer['role_id'],
                'mail_sent_order': signer['mail_sent_order'],
            }) for signer in signers],
            'reference': reference,
            'subject': subject,
            'message': message,
            'message_cc': message_cc,
            'attachment_ids': [Command.set(attachment_ids.ids)],
            'validity': self.validity,
            'reminder': self.reminder,
            'reminder_enabled': self.reminder_enabled,
            'reference_doc': reference_doc,
            'certificate_reference': self.certificate_reference,
            'send_channel': send_channel,
        })
        sign_request.message_subscribe(partner_ids=cc_partner_ids)
        return sign_request

    def _create_log_and_close(self, request):
        self._create_request_log_note(request)
        if self.activity_id:
            self._activity_done()

        if not self.reference_doc:
            return self.env['ir.actions.actions']._for_xml_id('sign.sign_request_action')

        # redirect to the record linked to reference_doc
        next_action = request.get_close_values().get('action')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': self.env._("Request sent successfully"),
                'next': next_action or {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def send_request(self):
        self.ensure_one()
        request = self.create_request()
        return self._create_log_and_close(request)

    def _create_request_log_note(self, request):
        if request.reference_doc:
            model = request.reference_doc and self.env['ir.model']._get(request.reference_doc._name)
            if model.is_mail_thread:
                body = self.env._("A signature request has been linked to this document: %s", request._get_html_link())
                request.reference_doc.message_post(body=body)
                body = self.env._("%s has been linked to this sign request.", request.reference_doc._get_html_link())
                request.message_post(body=body)

    def sign_directly(self):
        self.ensure_one()
        request = self.create_request()
        if self.activity_id:
            self._activity_done()
        if self.env.context.get('sign_all'):
            # Go back to document if it exists
            return request.go_to_signable_document(request.request_item_ids)
        return request.go_to_signable_document()

    def _get_user_signature(self, user, signature_type):
        """
        This function returns the signature or initials of a user (in this case the first). Returns False if signature or initials are not present.

        :param signature_type: can be 'sign_signature' or 'sign_initials' and inticates what we want to obtain.
        :return: returns the signature/initials if present or False if not or if signature_type is an invalid value.
        """
        if all(self.mapped('is_user_signer')) and signature_type in ['sign_signature', 'sign_initials']:
            return user[signature_type]
        return False

    @api.depends("template_id", "signer_ids")
    def _compute_only_autofill_readonly(self):
        """
        Computes the flag indicating if all the fields in a request are autofillable/constant(readonly).

        :return: nothing, sets the value in the only_autofill_readonly field.
        """
        # TODO master: clean this as it is only needed for download button (invisible for more than one signer)
        item_type_to_field = {
            'signature': 'sign_signature',
            'initial': 'sign_initials',
        }
        for request in self:
            role_to_user_map = {signer.role_id.id: signer.partner_id.main_user_id for signer in self.signer_ids}
            item_auto_fill_values = []
            for item in request.template_id.sign_item_ids:
                user = role_to_user_map.get(item.responsible_id.id)
                res = False
                constant_item = item.constant or item.type_id.sudo().auto_field or item.type_id.name == 'Date'
                if constant_item:
                    res = True
                elif item.type_id.item_type in item_type_to_field and user == self.env.user:
                    sign_field = item_type_to_field[item.type_id.item_type]
                    res = bool(user[sign_field])
                item_auto_fill_values.append(res)
            request.only_autofill_readonly = all(item_auto_fill_values)

    @api.depends("only_autofill_readonly", "signers_count", "is_user_signer")
    def _compute_display_download_button(self):
        """
        Computes the flag indicating if the download button should be shown in the wizard.

        :return: nothing, sets the value in the display_download_button field.
        """
        for wiz in self:
            wiz.display_download_button = (
                wiz.only_autofill_readonly
                and (wiz.signers_count == 1)
                and wiz.is_user_signer
            )

    def quick_sign(self):
        """
        Is triggered by the Download button, implements the quick-sign flow by retrieving the values needed to fill the fields, filling them, creating the finished document, downloading it and redirecting to the view of the model the user was coming from (sign requests can be made from other apps too).

        :return: triggers an action which downloads the completed document and redirects to the correct view.
        """
        # Create the sign request
        request = self.create_request()

        # Build a dictionary matching the fields that exist in the document with their properties.
        # The keys in the dictionary are the stringified version of the ids because that's how the
        # _fill function expects them later.
        sign_values = {}
        for item in self.template_id.sign_item_ids:
            sign_values[str(item.id)] = {
                "name": item.name,
                "type_id": item.type_id.id,
                "auto_field": item.type_id.sudo().auto_field,
                "type_name": item.name,
            }

        # Build the dictionary with the information taken from the user profile as the _fill function expects it
        sign_request_item = request.request_item_ids
        corrected_dict = sign_values.copy()
        frames = {}
        for key, value in sign_values.items():
            corrected_dict[key] = value["name"]
            # All autofillable fields except for Signature, Initials and Date have an auto_field property set which can be used to get the value from the profile
            if value.get("auto_field"):
                corrected_dict[key] = sign_request_item._get_auto_field_value({
                    "id": value.get("type_id"),
                    "auto_field": value.get("auto_field")
                })
            # Signatures and Initials need a different procedure because of the fact that the contents are images and they might need frames and hashes
            elif value.get("type_name") in ["Signature", "Initials"]:
                signature_field_name = 'sign_signature' if value.get("type_name") == "Signature" else 'sign_initials'
                user_signature = sign_request_item._get_user_signature(signature_field_name)
                user_signature_frame = sign_request_item.sudo()._get_user_signature_frame(signature_field_name + '_frame')
                corrected_dict[key] = 'data:image/png;base64,%s' % user_signature.decode() if user_signature else False
                frames[key] = {
                    'frameValue': 'data:image/png;base64,%s' % user_signature_frame.decode() if user_signature_frame else False,
                    'frameHash': False,
                }
            # The Date field can be autofilled but doesn't have a auto_field because it's always filled with today's date
            elif value.get("type_name") == "Date":
                corrected_dict[key] = format_date(self.env, fields.Date.today())

        # Fill the fields with the values contained in corrected_dict, set the request state as signed and generate the document.
        sign_request_item.sudo()._sign(corrected_dict, frame=frames)

        # Trigger the download and the redirection with a single custom action
        # The reference_doc tells us if the request has been made from somewhere outside of Sign (other apps)
        url = f"/sign/download/{request.id}/{request.access_token}/completed"
        if self.reference_doc:
            view_record = self.reference_doc
            action = {
                'type': 'ir.actions.client',
                'tag': 'sign_download_document_and_return',
                'params': {
                    'url': url,
                    'res_model': view_record._name,
                    'res_id': view_record.id,
                    'view_mode': 'form'
                }
            }
        else:
            action = {
                'type': 'ir.actions.client',
                'tag': 'sign_download_document_and_return',
                'params': {
                    'url': url,
                    'redirect_to': 'sign.sign_request_action'
                }
            }
        return action
