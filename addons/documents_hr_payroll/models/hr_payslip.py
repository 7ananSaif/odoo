# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'documents.mixin']

    document_access_url = fields.Char(compute="_compute_document_access_url")

    def action_resend_payslips(self, notify=False):
        def show_notification(notification_type, message):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Send Payslip By Email"),
                    'type': notification_type,
                    'message': message
                }
            }

        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(_('You can not send the documents link to the employee.'))
        payslips_sudo = self.sudo()
        if any(payslip.state not in ['validated', 'paid'] for payslip in payslips_sudo):
            return show_notification('warning', _('A payslip should be validated or paid to be sent to the employee.'))
        invalid_employees = payslips_sudo.employee_id.filtered(lambda e: not (e.private_email or e.work_email))
        if invalid_employees:
            raise UserError(
                _('Employee\'s private or work email must be set to use "Send By Email" function:\n%s',
                  '\n'.join(invalid_employees.mapped('name'))))

        payslip_without_documents = payslips_sudo.filtered(lambda p: not p.document_access_url)
        for payslip in (payslips_sudo - payslip_without_documents):
            template = payslip._get_email_template()
            template.send_mail(payslip.id, email_layout_xmlid='mail.mail_notification_light')
            payslip.message_post(body=_('The payslip has been re-sent to the employee.'))

        if not notify and not payslip_without_documents:  # refresh the form view
            return True

        message = _("Some payslips could not be resend as they do not have related document") \
            if payslip_without_documents else (
            _("%s Payslip(s) correctly sent.", len(payslips_sudo)))
        notification_type = "warning" if payslip_without_documents else "success"
        return show_notification(notification_type, message)

    def _get_document_vals_access_rights(self):
        """ All payslips should be accessible in 'Anyone with the link' to make the link permanent.
        The document must be still accessible even if the employee and its user (if any) are archived."""
        return {
            'access_via_link': 'view',
            'access_internal': 'none',
            'is_access_via_link_hidden': True,
        }

    def _get_document_access_ids(self):
        return [(self._get_document_partner(), ('view', False))]

    def _get_document_tags(self):
        return self.company_id.documents_hr_payslips_tags

    def _get_document_partner(self):
        return self.employee_id.user_id.partner_id or self.employee_id.work_contact_id

    def _get_document_owner(self):
        return self.employee_id.user_id or super()._get_document_owner()

    def _get_document_folder(self):
        return super()._get_document_folder() if self.employee_id.user_id else self.company_id._get_or_create_worker_payroll_folder()

    def _check_create_documents(self):
        return self._get_document_partner().id and (bool(self.employee_id.user_id) or self.company_id.documents_hr_settings)

    def _get_email_template(self):
        return self.env.ref(
            'documents_hr_payroll.mail_template_new_payslip', raise_if_not_found=False
        ) if self._check_create_documents() else None

    def _compute_document_access_url(self):
        documents = self.env["documents.document"].search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            order='res_id, id desc'
        )
        access_url_per_payslip = dict()
        for document in documents:
            if document.res_id not in access_url_per_payslip:  # keep last document for each payslip
                access_url_per_payslip[document.res_id] = document.access_url
        for payslip in self:
            payslip.document_access_url = access_url_per_payslip.get(payslip.id)

    @api.model
    def _cron_generate_pdf(self, batch_size=False):
        is_rescheduled = super()._cron_generate_pdf(batch_size=batch_size)
        if is_rescheduled:
            return is_rescheduled

        # Post declarations from mixin
        lines = self.env['hr.payroll.employee.declaration'].search([('pdf_to_post', '=', True)])
        if lines:
            BATCH_SIZE = batch_size or 30
            lines_batch = lines[:BATCH_SIZE]
            lines_batch._post_pdf()
            lines_batch.write({'pdf_to_post': False})
            # if necessary, retrigger the cron to generate more pdfs
            if len(lines) > BATCH_SIZE:
                self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
                return True
        return False
