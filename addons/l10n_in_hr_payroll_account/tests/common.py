# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon

@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollAccountCommon(TestPayrollCommon):

    def setUp(self):
        super(TestPayrollAccountCommon, self).setUp()

        self.account_journal = self.env['account.journal'].create({
            'name' : 'MISC',
            'code' : 'MSC',
            'type' : 'general',
            'company_id': self.company_in.id,
        })
        self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').journal_id = self.account_journal
        self.contract_rahul.structure_type_id = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay')
        self.contract_jethalal.structure_type_id = self.env.ref('l10n_in_hr_payroll.hr_payroll_salary_structure_type_ind_emp_pay')
