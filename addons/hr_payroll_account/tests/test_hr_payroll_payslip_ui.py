from odoo.addons.hr_payroll_account.tests.test_hr_payroll_account import TestHrPayrollAccountCommon
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install', 'payslip_ui')
class TestPayslipUi(TestHrPayrollAccountCommon, HttpCase):
    def test_ui_payslip_list_header_buttons(self):
        """Test payslip list header buttons."""
        self.user_admin = self.env.ref('base.user_admin')
        self.user_admin.company_ids |= self.company_us
        self.user_admin.write({
            'company_id': self.env.company.id,
            'email': 'mitchell.admin@example.com',
        })
        self.start_tour("/odoo", 'hr_payroll_view_header_buttons_tour', login='admin')
