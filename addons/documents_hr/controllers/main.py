# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http

from odoo.addons.sign.controllers.main import Sign
from odoo.http import request


class SignContract(Sign):

    @http.route()
    def sign(self, sign_request_id, token, sms_token=False, signature=None, **kwargs):
        """ Generate documents when a sign Request is fully completed
        and the hr_contract_sign is installed.
        """
        result = super().sign(sign_request_id, token, sms_token=sms_token, signature=signature, **kwargs)
        if 'sign_request_ids' not in request.env['hr.employee']:
            return result
        request_item = request.env['sign.request.item'].sudo().search([('access_token', '=', token)])
        is_completed = all(state == 'completed' for state in request_item.sign_request_id.request_item_ids.mapped('state'))
        signature_request_tag = request.env.ref('documents_hr.document_tag_signature_request', raise_if_not_found=False)
        if not is_completed:
            return result

        employee = request.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('sign_request_ids', 'in', request_item.sign_request_id.ids)])
        if employee and employee.company_id.documents_hr_settings and employee.hr_employee_folder_id:
            sign_request_sudo = request_item.sign_request_id.sudo()
            sign_request_sudo._generate_completed_documents()

            employee_partner = employee.work_contact_id or employee.user_id.partner_id
            owner = (
                employee.user_id or
                employee.search([('work_contact_id', '=', employee_partner.id)]).user_id or
                employee.version_id.hr_responsible_id or
                request_item.create_uid
            )

            request.env['documents.document'].sudo().create([{
                'partner_id': employee_partner.id,
                'owner_id': owner.id,
                'datas': doc.file,
                'name': f'{sign_request_sudo.display_name}/{doc.document_id.name}',
                'folder_id': employee.hr_employee_contract_folder_id.id,
                'tag_ids': [(4, signature_request_tag.id)] if signature_request_tag else [],
                'res_id': employee.id,
                'res_model': 'hr.employee',  # Security Restriction to contract managers
            } for doc in sign_request_sudo.completed_document_ids])

        versions = request.env['hr.version'].sudo().with_context(active_test=False).search([
            ('sign_request_ids', 'in', request_item.sign_request_id.ids)]).sorted('date_start', reverse=True)
        version = versions[0] if versions else False
        if version and version.company_id.documents_hr_settings and version.employee_id.hr_employee_folder_id:
            sign_request_sudo = request_item.sign_request_id.sudo()
            sign_request_sudo._generate_completed_documents()

            employee = version.employee_id
            employee_partner = employee.work_contact_id or employee.user_id.partner_id
            owner = (employee.user_id
                     or employee.search([('work_contact_id', '=', employee_partner.id)]).user_id
                     or version.hr_responsible_id)
            request.env['documents.document'].sudo().create([{
                'partner_id': employee_partner.id,
                'owner_id': owner.id,
                'datas': doc.file,
                'name': f'{sign_request_sudo.display_name}/{doc.document_id.name}',
                'folder_id': version.employee_id.hr_employee_contract_folder_id.id,
                'tag_ids': [(4, signature_request_tag.id)] if signature_request_tag else [],
                'res_id': version.id,
                'res_model': 'hr.version',  # Security Restriction to contract managers
            } for doc in sign_request_sudo.completed_document_ids])
        return result
