from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def get_documents_operation_add_destination(self):
        self.ensure_one()
        if (project := (
            self.env['project.project'].browse(self.res_id)
            if self.res_model == 'project.project'
            else self.env['project.task'].browse(self.res_id).project_id
            if self.res_model == 'project.task'
            else False
        )):
            return {
                'destination': str(project.documents_folder_id.id),
                'display_name': project.documents_folder_id.display_name,
            }
        return super().get_documents_operation_add_destination()
