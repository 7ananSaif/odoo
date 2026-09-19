from odoo import fields, models, _


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    other_input_type_code = fields.Char(related="other_input_type_id.code", string="Other Input Type Code")

    def action_create_loan_payslip(self):
        """
        Create a payslip for the loan.
        """
        payslips_data = []
        for employee in self.employee_ids:
            payslips_data.append({
                'name': _('Loan Payslip for %s', employee.name),
                'employee_id': employee.id,
                'date_from': self.date_start,
                'struct_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_salary_advance_and_loan').id,
                'input_line_ids': [(0, 0, {
                    'name': _('Loan'),
                    'amount': self.total_amount,
                    'input_type_id': self.env.ref('l10n_sa_hr_payroll.l10n_sa_input_loan_deduction').id,
                })],
            })
        payslips = self.env['hr.payslip'].create(payslips_data)
        payslips.message_post(
            body=_("Loan payslip created from this attachment: %s", self._get_html_link()),
        )

        if len(payslips) > 1:
            # If multiple payslips are created, return the action to open the list view
            return {
                'type': 'ir.actions.act_window',
                'name': _('Loan Payslips'),
                'res_model': 'hr.payslip',
                'view_mode': 'list,form',
                'domain': [('id', 'in', payslips.ids)],
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Loan Payslip'),
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'res_id': payslips.id,
            'target': 'current',
        }
