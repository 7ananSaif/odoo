from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class DocumentsOperation(models.TransientModel):
    _name = 'documents.operation'
    _description = "Documents Operation"

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if 'destination' in fields and not result.get('destination'):
            if self.env.user.share:
                if first_folder := self.get_any_editor_destination():
                    result['destination'] = str(first_folder[0]["id"])
                    result['display_name'] = first_folder[0]["display_name"]
                else:
                    raise UserError(self.env._("You do not have editor access to any folder."))
            else:
                result['destination'] = 'MY'
                result['display_name'] = self.env._('My Drive')
        return result

    operation = fields.Selection([
        ('move', 'Move'), ('shortcut', 'Create shortcuts'), ('copy', 'Duplicate to'),
        ('add', 'Add attachment to Documents')
    ], required=True)
    document_ids = fields.Many2many('documents.document', string="Documents")
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")

    destination = fields.Char(string='Destination', required=True)
    destination_children_ids = fields.One2many('documents.document', string='Siblings', compute="_compute_destination_children_ids")

    # Destination-related fields updated by the client for the client - do not use in the backend. No need
    # for compute/search because all is already fetched for the searchpanel and must be kept locally consistent
    display_name = fields.Char(string='Destination Display Name', compute=None, search=None)
    user_permission = fields.Selection(
        [('edit', 'Editor'), ('view', 'Viewer'), ('none', 'None')], string='Destination User Permission',
        default="edit", required=True)
    access_internal = fields.Char(string='Destination Access Internal')
    access_via_link = fields.Char(string="Destination Access Via Link")
    is_access_via_link_hidden = fields.Boolean(string="Destination Link Access Hidden")

    @api.depends('destination')
    def _compute_destination_children_ids(self):
        locations_to_targets = {}
        if wizards_with_folders_locations := self.filtered(lambda w: w.destination.isnumeric()):
            folders = self.env['documents.document'].search_fetch(
                Domain('id', 'in', wizards_with_folders_locations.mapped(lambda w: int(w.destination))),
                ['shortcut_document_id']
            )
            for wizard, folder in zip(wizards_with_folders_locations, folders):
                locations_to_targets[wizard] = folder.shortcut_document_id.id or folder.id
        for wizard in self:  # for simplicity, likely never called in batch
            domain = Domain('user_folder_id', '=', locations_to_targets.get(wizard) or wizard.destination) \
                     & Domain('type', '!=', 'folder')
            wizard.destination_children_ids = self.env['documents.document'].search(domain)

    def action_confirm(self):
        self.ensure_one()
        if self.operation == 'move':
            self.document_ids.user_folder_id = self.destination
        elif self.operation == 'copy':
            self.document_ids.copy({"user_folder_id": self.destination})
        elif self.operation == 'add' and self.attachment_id:
            if self.attachment_id.type not in dict(self.env['documents.document']._fields['type'].selection):
                raise UserError(self.env._("Unsupported attachment type: %s", self.attachment_id.type))
            attachment_copy = self.attachment_id.copy({'res_model': False, 'res_id': False})
            self.env['documents.document'].create({
                "attachment_id": attachment_copy.id,
                "type": attachment_copy.type,
                "user_folder_id": self.destination
            })
        elif self.operation == 'shortcut':
            self.document_ids.action_create_shortcut(location_user_folder_id=self.destination)
        else:
            raise UserError(self.env._("Invalid operation"))

    @api.readonly
    @api.model
    def get_any_editor_destination(self):
        return self.env["documents.document"].search_read(
            [('type', '=', 'folder'), ('shortcut_document_id', '=', False), ('user_permission', '=', 'edit')],
            ['id', 'display_name'], limit=1,
        )
