# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_project_folder_id = fields.Many2one(
        'documents.document',
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False)]", check_company=True,
        related='company_id.documents_project_folder_id', readonly=False, string="Project Folder",
    )
