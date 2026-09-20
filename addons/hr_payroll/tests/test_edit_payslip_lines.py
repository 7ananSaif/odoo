# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase

@tagged('-at_install', 'post_install', 'payslip_line')
class TestPayslipLineEdit(TestPayslipBase, HttpCase):
    def test_ui(self):
        """ Test editing payslip line flow"""
        self.user_admin = self.env.ref('base.user_admin')
        self.user_admin.company_ids |= self.company_us
        self.user_admin.write({
            'company_id': self.env.company.id,
            'email': 'mitchell.admin@example.com',
        })
        self.richard_emp.version_ids[0].wage = 1234

        richard_payslip = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': self.richard_emp.id
        })
        richard_payslip.compute_sheet()
        self.start_tour("/odoo", 'hr_payroll_edit_payslip_lines_tour', login='admin')
