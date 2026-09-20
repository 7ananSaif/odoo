from odoo import _, api, Command, fields, models


class DocumentsSharing(models.TransientModel):
    _name = 'documents.sharing'
    _description = "Documents Sharing"

    document_ids = fields.Many2many('documents.document', ondelete='cascade', readonly=True)
    share_access_ids = fields.One2many('documents.sharing.access', 'documents_sharing_id', required=True)

    # Rights edition
    access_internal = fields.Selection('_get_role_options', string="Internal users", required=True)
    access_internal_help = fields.Char(compute="_compute_access_internal_help")
    access_via_link = fields.Selection('_get_role_options', string="Access through link", required=True)
    access_via_link_help = fields.Char(compute="_compute_access_via_link_help")
    access_via_link_mode = fields.Selection('_get_access_via_link_mode', string="Discoverable", required=True)
    is_access_modified = fields.Boolean("Modified", compute="_compute_is_access_modified")

    # Invitation
    invite_role = fields.Selection(
        [('view', 'Viewer'), ('edit', 'Editor')],
        string='Role', default='view', required=True)
    invite_notify = fields.Boolean("Notify", default=True)
    invite_notify_message = fields.Html("Notification Message")
    invite_partner_ids = fields.Many2many('res.partner')

    # Additional readonly fields for displaying information
    access_urls = fields.Char("Access URLs", compute="_compute_ui_values")
    is_single = fields.Boolean("Single", compute="_compute_ui_values")
    is_folder_only = fields.Boolean("Folder Only", compute="_compute_ui_values")
    is_readonly = fields.Boolean("Readonly", compute="_compute_ui_values")
    has_warning_link_with_more_rights = fields.Char(compute="_compute_has_warning_link_with_more_rights")
    has_warning_partners_without_access = fields.Char(compute="_compute_has_warning_partners_without_access")
    owner_id = fields.Many2one("res.users", string="Owner of all documents", compute="_compute_ui_values")

    WRITE_VALUE_PREFIX = 'write_'

    @api.model
    def _add_write_options(self, selection_options):
        """Add write options to the given options list.

        For each existing option, adds a corresponding option with the prefix WRITE_VALUE_PREFIX (except for "mixed").
        Selecting a 'write_' option indicates that a change has been made."""
        new_options = []
        for code, label in selection_options:
            new_options.append((code, label))
            if code != 'mixed':
                new_options.append((f'{self.WRITE_VALUE_PREFIX}{code}', label))
        return new_options

    @api.model
    def _get_role_options(self):
        return self._add_write_options([('view', _('Viewer')), ('edit', _('Editor')),
                                        ('none', _('None')), ('mixed', _('Mixed rights'))])

    @api.model
    def _get_access_via_link_mode(self):
        return self._add_write_options([('mixed', _('Mixed values')),
                                        ('link_required', _('No')),
                                        ('discoverable', _('Yes'))])

    @api.depends_context('uid')
    @api.depends('document_ids')
    def _compute_ui_values(self):
        for record in self:
            documents = record.document_ids
            document0 = documents[:1]
            record.is_single = len(documents) == 1
            record.access_urls = ', '.join(d.access_url for d in documents)
            owner_is_multi = any(d.owner_id != document0.owner_id for d in documents)
            record.owner_id = document0.owner_id if not owner_is_multi else False
            record.is_folder_only = all(d.type == 'folder' for d in documents)
            record.is_readonly = any(d.user_permission != 'edit' for d in documents)

    @api.depends('access_internal', 'document_ids')
    def _compute_access_internal_help(self):
        for record in self:
            if record.access_internal.endswith('view'):
                if record.is_folder_only:
                    record.access_internal_help = _("Can only view contents. Cannot add, modify, or delete items.")
                else:
                    record.access_internal_help = _("Can only view. Cannot rename, move, or delete.")
            elif record.access_internal.endswith('edit'):
                if record.is_folder_only:
                    record.access_internal_help = _("Can add, modify, and delete files within this folder.")
                else:
                    record.access_internal_help = _("Can modify, delete, and rename.")
            elif record.access_internal == 'mixed':
                record.access_internal_help = _('Keep the values as is (multiple values)')
            else:  # None
                record.access_internal_help = _('Only people with access can open with the link')

    @api.depends('access_via_link', 'document_ids')
    def _compute_access_via_link_help(self):
        for record in self:
            if record.access_via_link.endswith('view'):
                if record.is_folder_only:
                    record.access_via_link_help = _("Can only view contents. Cannot add, modify, or delete items.")
                else:
                    record.access_via_link_help = _("Can only view. Cannot rename, move, or delete.")
            elif record.access_via_link.endswith('edit'):
                if record.is_folder_only:
                    record.access_via_link_help = _("Can add, modify, and delete files within this folder.")
                else:
                    record.access_via_link_help = _("Can modify, delete, and rename.")
            elif record.access_via_link == 'mixed':
                record.access_via_link_help = _('Keep the values as is (multiple values)')
            else:  # None
                record.access_via_link_help = _('No one on the internet can access')

    @api.depends('access_internal', 'access_via_link', 'access_via_link_mode',
                 'share_access_ids', 'share_access_ids.role',
                 'share_access_ids.original_expiration_date', 'share_access_ids.expiration_date',
                 'share_access_ids.is_deleted')
    def _compute_is_access_modified(self):
        for record in self:
            record.is_access_modified = bool(record._get_update_rights_params())

    @api.depends('access_internal', 'access_via_link', 'share_access_ids.role', 'invite_partner_ids')
    def _compute_has_warning_link_with_more_rights(self):
        for record in self:
            record.has_warning_link_with_more_rights = (
                    not record.invite_partner_ids and record.access_via_link.endswith('edit') and (
                    record.access_internal.endswith('view') or any(a.role.endswith('view') for a in record.share_access_ids)))

    @api.depends('access_via_link', 'invite_partner_ids', 'share_access_ids.partner_id.user_ids')
    def _compute_has_warning_partners_without_access(self):
        for record in self:
            record.has_warning_partners_without_access = any(r.has_warning_no_access for r in record.share_access_ids)

    def action_update_rights(self):
        self.ensure_one()
        self.document_ids.action_update_access_rights(
            **self._get_update_rights_params(), no_propagation=not self.is_folder_only)
        return self.action_open(self.document_ids.ids)

    def action_invite_members(self):
        self.ensure_one()
        if not self.invite_partner_ids:
            params = {
                'title': _('No partners'),
                'message': '',
                'type': 'warning',
            }
        elif self.invite_partner_ids.filtered(lambda p: not p.email):
            params = {
                'title': _('Some emails are missing'),
                'message': _('Please fill in the missing email addresses.'),
                'type': 'warning',
            }
        else:
            self.document_ids.action_update_access_rights(
                partners={
                    partner: (self.invite_role, None)
                    for partner in self.invite_partner_ids
                },
                no_propagation=not self.is_folder_only,
            )
            if self.invite_notify and (
                    share_template := self.env.ref('documents.mail_template_document_share', raise_if_not_found=False)):
                share_template.with_context(
                    documents=self.document_ids,
                    message=self.invite_notify_message or "").send_mail_batch(self.invite_partner_ids.ids)
            params = {
                'title': _('Successfully Shared'),
                'message': (
                    _('%s members added.', len(self.invite_partner_ids))
                    if len(self.invite_partner_ids) > 1
                    else _('Member added.')
                ),
                'type': 'success',
                'next': self.action_open(self.document_ids.ids),
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': params,
        }

    def action_allow_link_access(self):
        if self.has_warning_partners_without_access:
            self.access_via_link = f'{self.WRITE_VALUE_PREFIX}view'
            self.access_via_link_mode = f'{self.WRITE_VALUE_PREFIX}link_required'
        return self.action_update_rights()

    @api.model
    def action_open(self, document_ids):
        """Open documents sharing wizard on one or more documents."""
        if not document_ids:
            raise ValueError("Expected one or more documents.")
        documents = self.env['documents.document'].browse(document_ids).mapped(
            lambda d: d.shortcut_document_id if d.shortcut_document_id else d)
        document0 = documents[0]

        is_single_doc = len(documents) == 1
        all_partners = self._filtered_relevant_access(documents).partner_id
        access_by_partner_by_doc = {
            doc: {
                     access.partner_id: access.role
                     for access in self._filtered_relevant_access(doc)
                 } | ({doc.owner_id.partner_id: 'edit'} if doc.owner_id else {})
            for doc in documents
        }

        if is_single_doc:  # expiration only supported for single document
            expiration_per_partner = {
                access.partner_id: access.expiration_date
                for access in self._filtered_relevant_access(documents)
            }

        access_shares = []
        if any(d.owner_id != document0.owner_id for d in documents):  # there are no single owner of all the documents
            # Mixed owner -> add owner so that their rights appear "mixed" if not editor of the documents they don't own
            # Otherwise if there are only one owner, it will be displayed as such
            all_partners |= documents.owner_id.partner_id
        for partner in all_partners:
            role0 = access_by_partner_by_doc.get(documents[0], {}).get(partner)
            is_mixed = any(role0 != access_by_partner_by_doc.get(doc, {}).get(partner) for doc in documents[1:])
            expiration_date = expiration_per_partner.get(partner) if is_single_doc else False
            access_shares.append(Command.create(
                {
                    'expiration_date': expiration_date,
                    'original_expiration_date': expiration_date,
                    'partner_id': partner.id,
                    'role': 'mixed' if is_mixed else role0,
                }))

        values = {
            field: document0[field] if len(set(documents.mapped(field))) == 1 else 'mixed'
            for field in ('access_internal', 'access_via_link')
        }
        if len(set(documents.mapped('is_access_via_link_hidden'))) != 1:
            values['access_via_link_mode'] = 'mixed'
        elif document0.is_access_via_link_hidden:
            values['access_via_link_mode'] = 'link_required'
        else:
            values['access_via_link_mode'] = 'discoverable'

        doc_sharing = self.env['documents.sharing'].create([{
            'document_ids': documents.ids,
            'share_access_ids': access_shares,
            **values,
        }])

        if len(documents) == 1:
            name = _("Share: %(documentName)s", documentName=documents.name)
        else:
            name = _("Share: %(numberOfDocuments)s files", numberOfDocuments=len(documents))
        return {
            'context': {
                'dialog_size': 'medium',
            },
            'name': name,
            'res_id': doc_sharing.id,
            'res_model': 'documents.sharing',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [[False, 'form']],
        }

    @api.model
    def _filtered_relevant_access(self, documents):
        """Filter out expired access and non access of the documents (logs: role == False, owner access)"""
        return documents.access_ids.filtered(
            lambda a: a.role and a.partner_id != a.document_id.owner_id.partner_id
                      and (not a.expiration_date or a.expiration_date >= fields.Datetime.now()))

    def _get_update_rights_params(self):
        self.ensure_one()
        res = {}
        removed_access = self.share_access_ids.filtered('is_deleted')
        # Modification of the expiration date is not supported when multiple document are selected
        # In that case, expiration_date and original_expiration_date will be false and not modifiable in the UI
        # If a role is changed when multiple documents are selected, we keep the expiration (using None).
        modified_access = self.share_access_ids.filtered(
            lambda a: (a.role.startswith(self.WRITE_VALUE_PREFIX) or a.expiration_date != a.original_expiration_date)
                      and not a.is_deleted)
        partners = {
            access.partner_id: (access.role.removeprefix(self.WRITE_VALUE_PREFIX),
                                access.expiration_date if self.is_single else None)
            for access in modified_access
        }
        partners.update({
            access.partner_id: (False, False)
            for access in removed_access
        })
        if partners:
            res['partners'] = partners
        if self.access_internal.startswith(self.WRITE_VALUE_PREFIX):
            res['access_internal'] = self.access_internal.removeprefix(self.WRITE_VALUE_PREFIX)
        if self.access_via_link.startswith(self.WRITE_VALUE_PREFIX):
            res['access_via_link'] = self.access_via_link.removeprefix(self.WRITE_VALUE_PREFIX)
        if self.access_via_link_mode.startswith(self.WRITE_VALUE_PREFIX):
            res['is_access_via_link_hidden'] = self.access_via_link_mode == f'{self.WRITE_VALUE_PREFIX}link_required'
        return res
