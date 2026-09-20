# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import re
from datetime import timedelta

from reportlab.rl_config import TTFSearchPath

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command, Domain
from odoo.tools import misc, pdf
from odoo.tools.pdf import PdfReadError

from odoo.addons.sign.utils.pdf_handling import flatten_pdf

TTFSearchPath.append(misc.file_path("web/static/fonts/sign"))


class SignTemplate(models.Model):
    _name = 'sign.template'
    _description = "Signature Template"

    def _default_favorited_ids(self):
        return [(4, self.env.user.id)]

    document_ids = fields.One2many('sign.document', 'template_id', string="Documents", copy=True)
    name = fields.Char(required=True, default="New Template")
    sign_item_ids = fields.One2many('sign.item', 'template_id', string="Signature Items", compute='_compute_sign_item_ids', store=True, domain=[('page', '>', -1)])
    responsible_count = fields.Integer(compute='_compute_responsible_count', string="Responsible Count")

    active = fields.Boolean(default=True, string="Active")
    favorited_ids = fields.Many2many('res.users', string="Favorited Users", relation="sign_template_favorited_users_rel", default=_default_favorited_ids)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)

    sign_request_ids = fields.One2many('sign.request', 'template_id', string="Signature Requests")

    tag_ids = fields.Many2many('sign.template.tag', string='Tags')
    color = fields.Integer()
    redirect_url = fields.Char(string="Redirect Link", default="",
        help="Optional link for redirection after signature")
    redirect_url_text = fields.Char(string="Link Label", default="Close", translate=True,
        help="Optional text to display on the button link")
    signed_count = fields.Integer(compute='_compute_signed_in_progress_template')
    in_progress_count = fields.Integer(compute='_compute_signed_in_progress_template')
    signature_request_validity = fields.Integer(
        string="Default signature request validity",
        readonly=False,
        default=60,
        help="Specify the default validity period (in days) for signature requests. "
             "Set to 0 for requests that don't expire.")
    authorized_ids = fields.Many2many('res.users', string="Authorized Users", relation="sign_template_authorized_users_rel", default=_default_favorited_ids)
    group_ids = fields.Many2many("res.groups", string="Authorized Groups")
    has_sign_requests = fields.Boolean(compute="_compute_has_sign_requests", compute_sudo=True, store=True)

    is_sharing = fields.Boolean(compute='_compute_is_sharing', help='Checked if this template has created a shared document for you')
    # Other model integration
    model_id = fields.Many2one('ir.model', domain=[
        ('model', 'not in', ['sign.request', 'sign.template']),
        ('is_mail_thread', '=', 'True')
    ])
    model_name = fields.Char(related='model_id.model', string="Model Name")
    message = fields.Html("Message", help="Message to be sent to signers of the specified document")

    _signature_request_validity_check = models.Constraint(
        "CHECK(signature_request_validity IS NULL OR signature_request_validity >= 0)",
        "The number of days for expiration must be a positive value.",
    )

    @api.constrains('model_id')
    def _constraint_model_items(self):
        for template in self:
            if not template.model_name:
                continue
            model_names = template.document_ids.sign_item_ids.type_id.mapped('model_name')
            for model_name in model_names:
                if not model_name or model_name == 'res.partner':
                    continue
                if model_name != template.model_name:
                    raise UserError(self.env._(
                        "The template model %(t_name)s is incompatible with the signature fields %(model_name)s.",
                        model_name=model_name,
                        t_name=template.model_name,
                    ))

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        # Display favorite templates first
        domain = Domain.AND([[('display_name', operator, name)], domain or []])
        templates = self.search_fetch(domain, ['display_name'], limit=limit)
        if limit is None or len(templates) < limit:
            templates = templates.sorted(key=lambda t: self.env.user in t.favorited_ids, reverse=True)
        else:
            favorited_templates = self.search_fetch(
                domain & Domain('favorited_ids', '=', self.env.user.id),
                ['display_name'], limit=limit)
            templates = favorited_templates + (templates - favorited_templates)
            templates = templates[:limit]
        return [(template.id, template.display_name) for template in templates.sudo()]

    @api.depends('document_ids.sign_item_ids')
    def _compute_sign_item_ids(self):
        for template in self:
            template.sign_item_ids = [Command.set([
                item.id
                for document in template.document_ids
                for item in document.sign_item_ids
            ])]

    @api.depends('sign_item_ids.responsible_id')
    def _compute_responsible_count(self):
        for template in self:
            template.responsible_count = len(template.sign_item_ids.mapped('responsible_id'))

    @api.depends('sign_request_ids')
    def _compute_has_sign_requests(self):
        for template in self:
            template.has_sign_requests = bool(template.with_context(active_test=False).sign_request_ids)

    def _compute_signed_in_progress_template(self):
        sign_requests = self.env['sign.request']._read_group([('state', '!=', 'canceled')], ['state', 'template_id'], ['__count'])
        signed_request_dict = {template.id: count for state, template, count in sign_requests if state == 'signed'}
        in_progress_request_dict = {template.id: count for state, template, count in sign_requests if state == 'sent'}
        for template in self:
            template.signed_count = signed_request_dict.get(template.id, 0)
            template.in_progress_count = in_progress_request_dict.get(template.id, 0)

    @api.depends_context('uid')
    def _compute_is_sharing(self):
        sign_template_sharing_ids = set(self.env['sign.request'].search([
            ('state', '=', 'shared'), ('create_uid', '=', self.env.user.id), ('template_id', 'in', self.ids)
        ]).template_id.ids)
        for template in self:
            template.is_sharing = template.id in sign_template_sharing_ids

    @api.model
    def get_empty_list_help(self, help_message):
        if not self.env.ref('sign.template_sign_tour', raise_if_not_found=False):
            return '<p class="o_view_nocontent_smiling_face">%s</p>' % _('Upload a PDF')
        return super().get_empty_list_help(help_message)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for template, vals in zip(self, vals_list):
            if 'name' in vals and vals.get('name') == template.name or 'name' not in vals:
                vals['name'] = template._get_copy_name(template.name)

        return vals_list

    def update_document(self, document_id, attachment_data):
        """ Update a document in the template with a new one, preserving sign items.
        :param int document_id: ID of the document to replace
        :param dict attachment_data: Dictionary containing the new document data with name and datas
        :returns dict: Action to redirect to the new template
        """
        self.ensure_one()
        old_document = self.env['sign.document'].browse(document_id)

        if not old_document.exists() or old_document.template_id != self:
            raise UserError(_("The document you're trying to update doesn't exist or doesn't belong to this template."))

        # Check if the attachment data is valid PDF.
        self.env['sign.document']._check_pdf_data_validity(attachment_data['datas'])

        # Store the old document's sequence and create a copy of the template.
        # Find and delete the corresponding document in the new template.
        target_sequence = old_document.sequence
        new_template = self.copy()
        corresponding_doc = new_template.document_ids.filtered(
            lambda d: d.sequence == target_sequence
        )
        if corresponding_doc:
            corresponding_doc.unlink()

        # Create the new document directly with the correct sequence.
        # Copy sign items from old document to new document.
        attachment = self.env['ir.attachment'].create({
            'name': attachment_data['name'],
            'datas': attachment_data['datas'],
        })
        new_document = self.env['sign.document'].create({
            'attachment_id': attachment.id,
            'sequence': target_sequence,
            'template_id': new_template.id,
        })
        old_document._copy_sign_items_to(new_document)

        # Return action to open new template.
        return {
            'type': 'ir.actions.client',
            'tag': 'sign.Template',
            'name': _('Edit Template'),
            'params': {'id': new_template.id},
            'context': {},
        }

    @api.model
    def create_from_attachment_data(self, attachment_data_list, active=True):
        """
        Create a sign.template record with sign.document records from a list of attachment data.

        :param attachment_data_list: List of dictionaries, each with 'name' and 'datas' keys.
                                    Example: [{'name': 'asdf', 'datas': 'asdfasdfasdf23423'}, ...]
        :return: [ID of the newly created sign.template record, name of the template]
        :raises UserError: If the input list is empty or a dictionary is missing required keys.
        """

        # Update the document order sequence and flatten the PDF to make form fields read-only.
        count_sequence = len(self.document_ids)
        for att_data in attachment_data_list:
            att_data['sequence'] = count_sequence
            count_sequence += 1
            original_pdf_base64 = att_data.get('datas')
            if original_pdf_base64:
                att_data['datas'] = flatten_pdf(original_pdf_base64)
        context = {**self.env.context}
        if model_name := self.env.context.get('default_model_name'):
            model = self.env['ir.model']._get(model_name)
            context.update(default_model_id=model.id)
        template = self.with_context(context).create({
            'name': attachment_data_list[0]['name'],
            'active': active,
        })
        document_ids = self.env['sign.document'].create_from_attachment_data(attachment_data_list, template.id)
        if len(document_ids):
            template.write({
                'name': document_ids[0].name,
            })
        return {
            'id': template.id,
            'name': template.name,
        }

    def update_from_attachment_data(self, attachment_data_list):
        """
        Update the current sign.template record by adding sign.document records created from a list of attachment data.

        :param attachment_data_list: List of dictionaries, each with 'name' and 'datas' keys.
                                    Example: [{'name': 'asdf', 'datas': 'asdfasdfasdf23423'}, ...]
        :return: None. The sign.template record is updated in place.
        """
        # Update sequence for documents order.
        count_sequence = len(self.document_ids)
        for att_data in attachment_data_list:
            att_data['sequence'] = count_sequence
            count_sequence += 1

        self.env['sign.document'].create_from_attachment_data(attachment_data_list, self.id)

    def go_to_custom_template(self, sign_directly_without_mail=False):
        self.ensure_one()
        return {
            'name': self.name,
            'type': 'ir.actions.client',
            'tag': 'sign.Template',
            'context': self.env.context,
            'params': {
                'id': self.id,
                'sign_directly_without_mail': sign_directly_without_mail,
            },
        }

    def _check_send_ready(self):
        if any(item.type_id.item_type == 'selection' and not item.option_ids for item in self.sign_item_ids):
            raise UserError(self.env._("There are no values in selection field."))

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_existing_signature(self):
        if self.filtered(lambda template: template.has_sign_requests):
            raise UserError(_(
                "Oops! You can’t delete a template that has signature requests. It would be like asking "
                "your users to autograph air! How about archiving it instead?"))

    def get_radio_set_info_by_item_id(self, sign_item_ids=None):
        """
        :param list of sign item IDs (sign_item_ids)
        :return: dict radio_set_by_item_dict that maps each sign item ID in sign_item_ids of type "radio"
        to a dictionary containing num_options and radio_set_id of the radio set it belongs to.
        """
        radio_set_by_item_dict = {}
        if sign_item_ids:
            radio_items = self.sign_item_ids.filtered(lambda item: item.radio_set_id and item.id in sign_item_ids)
            radio_set_by_item_dict = {
                radio_item.id: {
                    'num_options': radio_item.num_options,
                    'radio_set_id': radio_item.radio_set_id.id,
                } for radio_item in radio_items
            }
        return radio_set_by_item_dict

    def update_from_pdfviewer(self, sign_items=None, deleted_sign_item_ids=None, name=None, document_id=None):
        """ Update a sign.template from the pdfviewer
        :param dict sign_items: {id (str): values (dict)}
            id: positive: sign.item's id in database (the sign item is already in the database and should be update)
                negative: negative random itemId(transaction_id) in pdfviewer (the sign item is new created in the pdfviewer and should be created in database)
            values: values to update/create
        :param list(str) deleted_sign_item_ids: list of ids of deleted sign items. These deleted ids may be
            positive: the sign item exists in the database
            negative: the sign item is new created in pdfviewer but removed before a successful transaction
        :return: dict new_id_to_item_id_map: {negative itemId(transaction_id) in pdfviewer (str): positive id in database (int)}
        """
        self.ensure_one()
        if self.has_sign_requests:
            return False
        if sign_items is None:
            sign_items = {}

        if name and document_id:
            document_id = self.env['sign.document'].search([('id', '=', document_id)])
            document_id.update_attachment_name(name)

        # update new_sign_items to avoid recreating sign items
        new_sign_items = dict(sign_items)
        sign_items_exist = self.sign_item_ids.filtered(lambda r: str(r.transaction_id) in sign_items)
        for sign_item in sign_items_exist:
            new_sign_items[str(sign_item.id)] = new_sign_items.pop(str(sign_item.transaction_id))
        new_id_to_item_id_map = {str(sign_item.transaction_id): sign_item.id for sign_item in sign_items_exist}

        # unlink sign items
        deleted_sign_item_ids = set() if deleted_sign_item_ids is None else set(deleted_sign_item_ids)
        self.sign_item_ids.filtered(lambda r: r.id in deleted_sign_item_ids or (r.transaction_id in deleted_sign_item_ids)).unlink()

        # update existing sign items
        for item in self.sign_item_ids.filtered(lambda r: str(r.id) in new_sign_items):
            str_item_id = str(item.id)
            if 'option_ids' in new_sign_items.get(str_item_id):
                new_option_ids = list(map(int, new_sign_items[str_item_id]['option_ids']))
                new_sign_items[str_item_id]['option_ids'] = [[6, 0, new_option_ids]]
            item.write(new_sign_items.pop(str_item_id))

        # create new sign items
        new_values_list = []
        for key, values in new_sign_items.items():
            if int(key) < 0:
                new_values_list.append(values)
        new_id_to_item_id_map.update(zip(new_sign_items.keys(), self.env['sign.item'].create(new_values_list).ids))

        return new_id_to_item_id_map

    @api.model
    def _get_copy_name(self, name):
        regex = re.compile(r'(.*?)((?:\(\d+\))?)((?:\.pdf)?)$')
        match = regex.search(name)
        name_doc = match.group(1)
        name_ver = match.group(2)
        name_ext = match.group(3)
        version = int(name_ver[1:-1]) + 1 if name_ver else 2
        return f"{name_doc}({version}){name_ext}"

    @api.model
    def rotate_pdf(self, template_id=None):
        template = self.browse(template_id)
        if template.has_sign_requests:
            return False

        template.datas = base64.b64encode(pdf.rotate_pdf(base64.b64decode(template.datas)))

        return True

    def open_requests(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Sign requests"),
            "res_model": "sign.request",
            "res_id": self.id,
            "domain": [["template_id", "in", self.ids]],
            "views": [[False, 'kanban'], [False, "form"]],
            "context": {'search_default_signed': True}
        }

    def open_shared_sign_request(self):
        self.ensure_one()
        shared_sign_request = self.sign_request_ids.filtered(lambda sr: sr.state == 'shared' and sr.create_uid == self.env.user)

        local_context = dict(self.env.context, default_sign_request_id=self.id)

        wizard = self.env["sign.request.share"].with_context(local_context).create({
            "template_id": self.id,
            "sign_request_id": shared_sign_request.id if shared_sign_request else False,
            "is_shared": bool(shared_sign_request)
        })

        return {
            "name": _("Share Document"),
            'type': 'ir.actions.act_window',
            "view_mode": "form",
            "target": "new",
            "res_model": "sign.request.share",
            "res_id": wizard.id,
            "views": [[False, "form"]],
        }

    def get_action_in_progress_requests(self):
        """ Get the in-progress sign requests related to this template. """
        sign_request_ids = self.env['sign.request'].search([('state', '=', 'sent'), ('template_id', '=', self.id)]).ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('In Progress Requests'),
            'res_model': 'sign.request',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', sign_request_ids)],
        }

    def get_action_signed_requests(self):
        """ Get the signed sign requests related to this template. """
        sign_request_ids = self.env['sign.request'].search([('state', '=', 'signed'), ('template_id', '=', self.id)]).ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signed Requests'),
            'res_model': 'sign.request',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', sign_request_ids)],
        }

    def stop_sharing(self):
        self.ensure_one()
        return self.sign_request_ids.filtered(lambda sr: sr.state == 'shared' and sr.create_uid == self.env.user).unlink()

    def trigger_template_tour(self):
        template = self.env.ref('sign.template_sign_tour')
        if template.has_sign_requests:
            template = template.copy({
                'favorited_ids': [Command.link(self.env.user.id)],
                'active': False,
                'sign_item_ids': False,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'sign.Template',
            'name': template.name,
            'params': {
                'id': template.id,
                'sign_directly_without_mail': False
            }
        }

    def action_duplicate(self):
        self.ensure_one()
        self.check_access('write')
        for document in self.document_ids:
            document.check_access('write')
        self.copy()

    ##################
    # PDF Rendering #
    ##################

    def action_template_preview(self, document_id):
        self.ensure_one()
        # We create the wizard here to have a proper id (not newID). The pdf_viewer widget needs it
        # to display the pdf in the iFrame
        wizard = self.env['sign.template.preview'].create({
            'template_id': self.id,
            'document_id': document_id,
        })
        return {
            'name': _("Template Preview"),
            'res_id': wizard.id,
            'type': 'ir.actions.act_window',
            'res_model': 'sign.template.preview',
            'target': 'new',
            'views': [[False, 'form']],
            'context': self.env.context,
        }

    def get_template_items_roles_info(self):
        """ Extract a unique list of role IDs and colors from self.sign_item_ids, adding an index. """
        self.ensure_one()
        roles_info = []
        for idx, role in enumerate(self.sign_item_ids.responsible_id.sorted()):
            roles_info.append({
                'id': idx,
                'name': role.name,
                'roleId': role.id,
                'colorId': idx,
                'assignTo': role.assign_to.avatar_128 or role.assign_to.avatar_1920 or '',
            })
        return roles_info

    def action_template_configuration(self):
        """ Open the template properties form view. """
        self.ensure_one()
        return {
            'name': "Edit Template Form",
            'type': "ir.actions.act_window",
            'res_model': "sign.template",
            'res_id': self.id,
            'views': [[False, "form"]],
            'context': self.env.context,
        }

    @api.model
    def create_sign_template_from_ir_attachment_data(self, attachment_id=False, res_id=False, res_model=False):
        """
        Create a sign.template record from an existing ir.attachment.

        :param attachment_id: The ID of the `ir.attachment` record to use as the source document.
        :param res_id: ID of the related record to link as reference.
        :param res_model: Model name of the related record to link as reference.
        :return: A tuple containing the ID and name of the newly created `sign.template`.
        """
        attachment = self.env['ir.attachment'].browse(attachment_id).exists()
        if not attachment:
            raise UserError(_("Attachment not found."))
        attachment_data = {
            'name': attachment.name,
            'datas': attachment.datas,
        }

        try:
            template_data = self.create_from_attachment_data([attachment_data], active=False)
        except (ValueError, PdfReadError) as e:
            raise UserError(self.env._("PDF File is corrupted. Please try with another file.")) from e

        return template_data['id'], template_data['name']

    def open_sign_send_dialog(self):
        """ Create and open dialog. This is needed to be able to compute the values without onchange and default.
        """
        context = dict(self.env.context)
        template = self and self[:1]
        default_activity_id = context.get('default_activity_id')
        is_activity = False
        if default_activity_id:
            activity = self.env['mail.activity'].browse(default_activity_id)
            if activity_template := activity.activity_type_id.default_sign_template_id:
                if activity_template.has_access('read'):
                    is_activity = True
                    template = activity_template
        context.update({'default_template_id': template and template.id})
        if template.exists() and not is_activity:
            # Hide the template_id field
            context.update({'default_has_default_template': True})
        if context.get('default_reference_doc'):
            context.update({'sign_from_record': True})
        if not context.get('default_model'):
            context.update({'default_model': 'sign.template'})
        if not context.get('default_res_ids'):
            context.update({'default_res_ids': self.ids})
        action = self.env['ir.actions.act_window']._for_xml_id('sign.action_sign_send_request')
        action.update({
            'context': context,
            'target': 'new',
        })
        return action

    @api.model
    def create_item_and_role(self, document_id, role_name):
        """ Create a new sign role and a corresponding dummy sign item. """
        role = self.env['sign.item.role'].create({'name': role_name})
        self.env['sign.item'].create({
            'document_id': document_id,
            'type_id': 1,
            'required': False,
            'responsible_id': role.id,
            'page': -1,
            'posX': -1,
            'posY': -1,
            'width': -1,
            'height': -1,
        })
        return role.id

    @api.autovacuum
    def _gc_sign_items(self):
        """ Garbage-collect dummy sign items (page < 0) that are older than one day,
        and remove sign roles that are no longer linked to any active sign items.
        """

        # Filter dummy items older than 1 day to avoid deleting roles that may still be
        # used in an ongoing sign request creation session.
        one_day_ago = fields.Datetime.now() - timedelta(days=1)
        dummy_items = self.env['sign.item'].search([('page', '<', 0), ('create_date', '<', one_day_ago)])

        active_items = self.env['sign.item'].search([('page', '>', -1)])
        roles_with_dummy_items = dummy_items.mapped('responsible_id')
        roles_with_active_items = active_items.mapped('responsible_id')
        unused_role_recordset = roles_with_dummy_items - roles_with_active_items
        dummy_items.unlink()
        unused_role_recordset.unlink()
