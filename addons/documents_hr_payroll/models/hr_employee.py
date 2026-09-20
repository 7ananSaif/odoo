from odoo import models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_resend_payslips(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(self.env._('You can not send the documents link to the employee.'))

        def show_notification(notification_type, message):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': self.env._("Resend All Employee's Payslips"),
                    'type': notification_type,
                    'message': message
                }
            }

        valid_payslips = self.slip_ids.filtered(lambda ps: ps.state in ['done', 'paid'] and ps.document_access_url)
        if not valid_payslips:
            return show_notification('warning', self.env._('There is no valid payslip to send to the employee.'))
        valid_payslips.action_resend_payslips(notify=False)
        return show_notification('success', self.env._('Payslips successfully sent to the employee.'))
