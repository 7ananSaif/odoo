# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_project_folder_id = fields.Many2one(
        'documents.document', string="Project Folder",
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False)]", check_company=True,
        default=lambda self: self.env.ref('documents_project.document_project_folder', raise_if_not_found=False),
        context=lambda env: {
            'default_type': 'folder',
            'default_folder_id': (env.ref('documents_project.document_project_folder', raise_if_not_found=False) or env['documents.document']).id,
        },
    )

    @api.constrains('documents_project_folder_id')
    def _check_documents_project_folder_id_company_id(self):
        if wrong_companies := self.filtered(lambda c: c.documents_project_folder_id.company_id.id not in {False, c.id}):
            companies_list = "\n- ".join(f"{company.name}: {company.documents_project_folder_id.name}"
                                         for company in wrong_companies)
            raise ValidationError(
                _("Company Project Folders cannot be linked to another company.%s", f'\n- {companies_list}')
            )
