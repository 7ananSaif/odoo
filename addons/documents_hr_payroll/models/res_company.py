# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_hr_payslips_tags = fields.Many2many(
        'documents.tag', 'payslip_tags_table')

    worker_payroll_folder_id = fields.Many2one(
        'documents.document', string="Worker Payroll Folder", check_company=True,
        domain=[('type', '=', 'folder'), ('shortcut_document_id', '=', False)],
        help="Folder used when an employee with no user exists in the company, "
             "to store their payroll documents in a centralized place.")

    def _generate_employee_documents_main_folders(self):
        """ Override from documents_hr module to add payslips related tags and permissions on the
        employee document folder of each company. """
        folders = super()._generate_employee_documents_main_folders()
        group_payroll_user = self.env.ref('hr_payroll.group_hr_payroll_user')
        payslip_tag = self.env.ref('documents_hr_payroll.documents_tag_payslips', raise_if_not_found=False)
        for company, folder in zip(self, folders):
            company.sudo().write({
                'documents_hr_payslips_tags': [(6, 0, payslip_tag.ids)] if payslip_tag else [],
            })
            payroll_users = group_payroll_user.all_user_ids.filtered(lambda user: folder.company_id in user.company_ids)
            folder.sudo().action_update_access_rights(
                access_internal='none', access_via_link='none', is_access_via_link_hidden=True,
                partners={partner.id: ('edit', False) for partner in payroll_users.partner_id})
        return folders

    def _get_used_folder_ids_domain(self, folder_ids):
        return super()._get_used_folder_ids_domain(folder_ids) | Domain('worker_payroll_folder_id', 'in', folder_ids)

    def _get_or_create_worker_payroll_folder(self):
        if not self.worker_payroll_folder_id:
            self.worker_payroll_folder_id = self.env['documents.document'].sudo().create({
                'name': self.env._("Payroll %s", self.name),
                'type': 'folder',
                'owner_id': False,
                'folder_id': self.documents_employee_folder_id.id,
            }).id
        return self.worker_payroll_folder_id
