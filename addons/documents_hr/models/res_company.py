# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_hr_settings = fields.Boolean(default=True)
    documents_employee_folder_id = fields.Many2one('documents.document', string="Employees Folder",
        domain=[('type', '=', 'folder'), ('shortcut_document_id', '=', False)], check_company=True)
    employee_subfolders = fields.Char(
        "Employees Subfolder",
        help='Comma separated list of folder names that need to be created under each employee folder.')
    documents_hr_contracts_tags = fields.Many2many('documents.tag', 'documents_hr_contracts_tags_table')

    def _get_used_folder_ids_domain(self, folder_ids):
        return super()._get_used_folder_ids_domain(folder_ids) | (
            Domain('documents_employee_folder_id', 'in', folder_ids) & Domain('documents_hr_settings', '=', True)
        )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._generate_employee_documents_main_folders()
        return companies

    def write(self, vals):
        """ Override to move all employee subfolders if the HR Employee folder has been modified in settings.
        And ensure that companies that was never configured get their employee subfolders. """
        subfolders_changed = vals.get('employee_subfolders')
        employees_without_subfolder = self.env['hr.employee']
        employees_with_subfolders = self.env['hr.employee']
        if vals.get('documents_employee_folder_id'):
            employees = self.env['hr.employee'].sudo().search([('company_id', 'in', self.ids)])
            # Might be that companies was never configured and no subfolder exists for employees.
            employees_without_subfolder = employees.filtered(lambda e: not e.hr_employee_folder_id)
            employees_with_subfolders = employees - employees_without_subfolder
            employees_with_subfolders.hr_employee_folder_id.folder_id = vals['documents_employee_folder_id']
            # done in two times otherwise the folder_id will propagate it's own access rights instead of the write values
            employees_with_subfolders.hr_employee_folder_id.write({
                'access_via_link': 'edit',
                'access_internal': 'none',
            })
        result = super().write(vals)
        if employees_without_subfolder:
            employees_without_subfolder._generate_employee_documents_folders(skip_subfolders=subfolders_changed)
        if subfolders_changed:
            self.env['hr.employee'].search([('company_id', 'in', self.ids)])._generate_employee_documents_subfolders()
        return result

    def _generate_employee_documents_main_folders(self):
        for company in self:
            company.sudo().documents_employee_folder_id = self.env['documents.document'].sudo().create({
                'name': company.env._('Employees - %s', company.name),
                'type': 'folder',
                'folder_id': False,
                'company_id': company.id,
                'is_access_via_link_hidden': True,
            })
        return self.mapped('documents_employee_folder_id')
