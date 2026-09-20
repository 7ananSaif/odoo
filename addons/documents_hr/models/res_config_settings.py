# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_hr_settings = fields.Boolean(
        related='company_id.documents_hr_settings', readonly=False, string="Human Resources")
    documents_employee_folder_id = fields.Many2one(
        'documents.document', domain=[('type', '=', 'folder'), ('shortcut_document_id', '=', False)],
        related='company_id.documents_employee_folder_id', readonly=False)
    employee_subfolders = fields.Char(
        "Employees Subfolder", related='company_id.employee_subfolders', readonly=False,
        help='Comma separated string of folder names that need to be created under each employee folder.')
    documents_hr_contracts_tags = fields.Many2many(
        'documents.tag', 'documents_hr_contracts_tags_table', related='company_id.documents_hr_contracts_tags',
        readonly=False, string="Contracts")
