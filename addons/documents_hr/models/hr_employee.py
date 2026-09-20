# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, ValidationError


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'documents.mixin']

    document_count = fields.Integer(compute='_compute_document_count', groups="hr.group_hr_user")
    hr_employee_folder_id = fields.Many2one('documents.document', string="HR Employee Folder", groups="base.group_system,hr.group_hr_user")
    hr_employee_contract_folder_id = fields.Many2one('documents.document', string="HR Employee Contract Folder", groups="base.group_system,hr.group_hr_user")

    def _get_document_folder(self):
        return self.hr_employee_folder_id if self.company_id.documents_hr_settings else False

    def _get_document_partner(self):
        return self.work_contact_id

    def _check_create_documents(self):
        return self.company_id.documents_hr_settings and super()._check_create_documents()

    def _compute_document_count(self):
        # FIX in 18.3, to remove when documents hr setting won't be optional anymore.
        if not self.hr_employee_folder_id:
            # Search everywhere if no employee folder configured.
            # Method not optimized for batches since it is only used in the form view.
            for employee in self:
                if employee.work_contact_id:
                    employee.document_count = self.env['documents.document'].search_count([
                        ('partner_id', '=', self.work_contact_id.id)
                    ])
                else:
                    employee.document_count = 0
            return
        document_count_by_folder = dict(self.env['documents.document']._read_group([
            ('id', 'child_of', self.hr_employee_folder_id.ids),
            ('type', '!=', 'folder')
        ], groupby=['folder_id'], aggregates=['__count']))

        document_count_by_employee_folder = {
            folder: sum(
                count for doc_folder, count in document_count_by_folder.items()
                if doc_folder.parent_path.startswith(folder.parent_path)
            ) for folder in self.hr_employee_folder_id
        }
        for employee in self:
            employee.document_count = document_count_by_employee_folder.get(employee.hr_employee_folder_id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._generate_employee_documents_folders()
        return employees

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals and len(self) == 1:
            # This makes no sense to rename multiple employees with the same name. This would probably be an error.
            # So we rename the folder only if one employee is renamed at a time.
            self.sudo().hr_employee_folder_id.write({'name': vals['name']})
        return result

    def action_open_documents(self):
        """ Open and display all the content of the employee subfolder under HR > Employee. """
        self.ensure_one()
        if not self.work_contact_id:
            raise ValidationError(_('You must have a contact linked to the employee in order to use Document\'s features.'))
        action = self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference')
        # If setting not activated, use the old filter -> Search everywhere
        if not self.company_id.documents_hr_settings:
            action['context'] = {
                'default_partner_id': self.work_contact_id.id,
                'searchpanel_default_folder_id': False,
                'default_res_id': self.id,
                'default_res_model': 'hr.employee',
            }
            return action
        if not self.hr_employee_folder_id:
            raise ValidationError(_('You must configure the HR Employee folder in document settings to use Document\'s features.'))
        if not self.env.user.has_groups('hr.group_hr_user'):
            raise AccessError(_('You cannot access the employee\'s folder.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.hr_employee_folder_id.sudo().access_url,
        }

    def _generate_employee_documents_folders(self, skip_subfolders=False):
        """ Employee document folder is meant to be used by HR only to store all the documents they need regarding the
         employee (E.g.: ID Card, Drive License, etc..). The employee does not have access to this folder,
         nor the documents inside it (by default at least) """
        employees = self.filtered('company_id.documents_employee_folder_id')
        folders = self.env["documents.document"].sudo().create([{
            'name': employee.name,
            'type': 'folder',
            'folder_id': employee.company_id.documents_employee_folder_id.id,
            'company_id': employee.company_id.id,
            'access_internal': 'none',
            'access_via_link': 'edit',
            'is_access_via_link_hidden': True,
            'owner_id': False,
        } for employee in employees])
        for employee, folder in zip(employees, folders):
            employee.hr_employee_folder_id = folder.id
            # create Contracts Subfolder
            if not employee.hr_employee_contract_folder_id:
                employee.hr_employee_contract_folder_id = self.env["documents.document"].sudo().create([{
                    'name': self.env._("Contracts"),
                    'type': 'folder',
                    'folder_id': employee.hr_employee_folder_id.id,
                    'company_id': employee.company_id.id,
                }])
        if not skip_subfolders:
            employees._generate_employee_documents_subfolders()

    def _generate_employee_documents_subfolders(self):
        """ Generate subfolders under the employee folder, following what is specified on the company
         -> res_config_settings.employee_subfolders
         Removing a folder name from the setting should not delete the folder if it's not empty.
         Existing folders should not be recreated.
         Only newly added folder name should generate a new subfolder.
         """
        Documents = self.env['documents.document']
        create_subfolders_vals = []
        subfolders_to_delete = Documents

        subfolders = Documents.search([
            ('type', '=', 'folder'),
            ('folder_id', 'in', self.hr_employee_folder_id.ids),
            ('id', 'not in', self.hr_employee_contract_folder_id.ids)])
        subfolders_by_employee_folder = subfolders.grouped('folder_id')
        for company in self.company_id:
            subfolder_names = [
                name for name in company.employee_subfolders.split(',') if name
            ] if company.employee_subfolders else []
            company_employees = self.filtered(lambda e: e.company_id == company and e.hr_employee_folder_id)
            for employee in company_employees:
                # Add new folders added to the list
                existing_subfolders = subfolders_by_employee_folder.get(employee.hr_employee_folder_id, Documents)
                added_subfolder_names = list(set(subfolder_names) - set(existing_subfolders.mapped('name')))
                for subfolder_name in added_subfolder_names:
                    create_subfolders_vals.append({
                        'name': subfolder_name.strip(),
                        'type': 'folder',
                        'folder_id': employee.hr_employee_folder_id.id,
                        'company_id': company.id,
                    })

                # Delete removed folder from the list.
                # -> Side effect : folders created manually that are still empty will be deleted.
                removed_subfolders_names = list(set(existing_subfolders.mapped('name')) - set(subfolder_names))
                subfolders_to_delete |= existing_subfolders.filtered(
                    lambda f: f.name in removed_subfolders_names and not f.children_ids)
        if create_subfolders_vals:
            self.env["documents.document"].sudo().create(create_subfolders_vals)
        subfolders_to_delete.unlink()

    def _get_employee_documents_token(self):
        self.ensure_one()
        return tools.hmac(
            self.env(su=True),
            "documents-hr-my-files",
            str(self.id),
        )

    def _get_documents_link_url(self):
        self.ensure_one()
        return f'{self.get_base_url()}/documents_hr/my_files/{self.id}/{self._get_employee_documents_token()}'
