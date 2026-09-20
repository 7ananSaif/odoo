from odoo import fields, models


class SignTemplate(models.Model):
    _name = 'sign.template'
    _inherit = ['sign.template', 'documents.unlink.mixin']

    def _default_folder_id(self):
        return self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False).id

    folder_id = fields.Many2one('documents.document', 'Signed Document Folder',
                                context=lambda env: {
                                    'default_type': 'folder',
                                    'default_folder_id': env.ref('documents_sign.document_sign_folder').id,
                                },
                                domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False)]")
    documents_tag_ids = fields.Many2many('documents.tag', string="Signed Document Tags")
