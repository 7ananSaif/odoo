from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_email_template(self):
        self.ensure_one()
        if self.country_code != 'CH':
            return super()._get_email_template()

        # We check for the employee contact if it has a portal_user linked to it
        if self.employee_id.user_id or (self.employee_id.work_contact_id and self.employee_id.work_contact_id.user_ids):
            return self.env.ref('hr_payroll.mail_template_new_payslip', raise_if_not_found=False)

        return self.env.ref('documents_hr_payroll.mail_template_new_payslip', raise_if_not_found=False)
