from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.fields import Command, Domain


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    @api.ondelete(at_uninstall=False)
    def unlink_except_sign_folder(self):
        sign_folder = self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False)
        if not sign_folder:
            return
        sign_folder_ancestors = set(map(int, sign_folder.sudo().parent_path.split('/')[:-1]))
        if sign_folder_ancestors & set(self.ids):
            raise UserError(_('The "%s" folder is required by the Sign application and cannot be deleted.',
                              sign_folder.name))

    @api.constrains('company_id')
    def _check_no_company_on_sign_folder(self):
        if not self.company_id:
            return
        if (sign_folder := self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False
                                        )) and sign_folder in self and sign_folder.company_id:
            raise UserError(_("You cannot set a company on the %s folder.", sign_folder.name))

    @api.constrains('active')
    def _archive_except_sign_folder(self):
        if all(d.active for d in self):
            return
        sign_folder = self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False)
        if sign_folder and sign_folder in self and not sign_folder.active:
            raise UserError(_("You cannot archive the Sign folder (%s).", sign_folder.name))

    def document_sign_create_sign_template(self, folder_id=False):
        if self.filtered(lambda doc: doc.type != 'binary' or doc.shortcut_document_id
                                    or not doc.mimetype or 'pdf' not in doc.mimetype.lower()):
            raise UserError(_("This action can only be applied on pdf document."))

        create_values = {
            'favorited_ids': [(4, self.env.user.id)],
            'folder_id': folder_id or self[0].folder_id.id,
        }

        all_tags = self.tag_ids
        if all_tags:
            create_values['documents_tag_ids'] = [Command.set(all_tags.ids)]

        template = self.env['sign.template'].create(create_values)
        self.env['sign.document'].create([{
            'attachment_id': doc.attachment_id.id,
            'template_id': template.id,
        } for doc in self])

        return template.go_to_custom_template(sign_directly_without_mail=True)

    def _get_gc_clear_bin_domain(self):
        return Domain.AND([
            super()._get_gc_clear_bin_domain(),
            [("res_model", "!=", "sign.request")],
            [("res_model", "!=", "sign.document")],
        ])

    @api.model
    def _data_embed_sign_create_sign_template_direct(self):
        action_sign = self.env.ref("documents_sign.ir_actions_server_create_sign_template_direct")
        if internal_folder := self.env.ref("documents.document_internal_folder", raise_if_not_found=False):
            self.action_folder_embed_action(internal_folder.id, action_sign.id)
        if inbox_folder := self.env.ref("documents.document_inbox_folder", raise_if_not_found=False):
            self.action_folder_embed_action(inbox_folder.id, action_sign.id)
