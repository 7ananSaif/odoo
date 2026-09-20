from odoo import models
from odoo.exceptions import ValidationError


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    def _get_unauthorized_root_document_owners_sudo(self):
        """ As portal users can be employees, and as they need to access their employee related documents
        via their "My drive", allow portal user that are linked to employee to own root documents """
        unauthorized_owners_sudo = super()._get_unauthorized_root_document_owners_sudo()
        return unauthorized_owners_sudo.with_context(active_test=False).filtered(lambda u: not u.employee_id)

    def _raise_if_used_folder(self):
        if folder_ids := self.filtered(lambda d: d.type == 'folder').ids:
            employees_folders_in_self = self.env['hr.employee'].sudo().search_count(
                ['|', ('hr_employee_folder_id', 'child_of', folder_ids),
                 ('hr_employee_contract_folder_id', 'child_of', folder_ids)], limit=1)
            if employees_folders_in_self:
                raise ValidationError(self.env._("Impossible to delete employee folder or employee 'Contract' folder"))
        return super()._raise_if_used_folder()
