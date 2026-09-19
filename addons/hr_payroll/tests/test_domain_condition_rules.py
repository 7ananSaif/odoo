# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests.common import tagged

from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('payslip_domain_condition')
class TestDomainCondition(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_2 = cls.env['res.company'].create({'name': 'Shrek Comp'})
        cls.shrek_emp = cls.env['hr.employee'].create({
            'name': 'Shrek',
            'company_id': cls.company_2.id,
            'date_version': date(2000, 4, 22),
            'contract_date_start': date(2000, 4, 22),
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })
        cls.shrek_contract = cls.shrek_emp.version_id

        cls.company_3 = cls.env['res.company'].create({'name': 'Donkey Comp'})
        cls.donkey_emp = cls.env['hr.employee'].create({
            'name': 'Donkey',
            'company_id': cls.company_3.id,
            'date_version': date(2000, 4, 22),
            'contract_date_start': date(2000, 4, 22),
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })
        cls.donkey_contract = cls.donkey_emp.version_id

    def _generate_payslip(self, date_from, struct, employee=None):
        date_to = date_from + relativedelta(months=1, days=-1)

        test_payslip = self.env['hr.payslip'].create({
            'name': 'Payslip for domain condition tests - ' + str(date_from),
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'struct_id': struct.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        test_payslip.compute_sheet()
        test_payslip.action_payslip_done()
        return test_payslip

    def _assert_rule_applied(self, payslip, rule_code, expected_amount):
        rule_line = payslip.line_ids.filtered(lambda l: l.code == rule_code) or 0
        self.assertTrue(rule_line, f"Rule line {rule_code} not found in payslip.")
        self.assertAlmostEqual(rule_line.total, expected_amount, delta=0.01,
                               msg=f"The total for {rule_code} should be {expected_amount} but is {rule_line.total}.")

    def _assert_rule_not_applied(self, payslip, rule_code):
        rule_line = payslip.line_ids.filtered(lambda l: l.code == rule_code)
        self.assertEqual(len(rule_line), 0, f"Rule line {rule_code} should not be applied in payslip.")

    def test_domain_01_basic(self):
        domain_test_structure_01 = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for domain test 01',
            'type_id': self.structure_type.id,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Always True Domain Rule',
            'code': 'DOMTRUE',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_01.id,
            'condition_select': 'domain',
            'condition_domain': "[]",
            'amount_select': 'fix',
            'amount_fix': 100.0,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Shrek Specific Domain Rule',
            'code': 'DOMSHREK',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_01.id,
            'condition_select': 'domain',
            'condition_domain': "[('employee_id.name', '=', 'Shrek')]",
            'amount_select': 'fix',
            'amount_fix': 200.0,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Always False Domain Rule',
            'code': 'DOMFALSE',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_01.id,
            'condition_select': 'domain',
            'condition_domain': "[('id', '=', 0)]",
            'amount_select': 'fix',
            'amount_fix': 300.0,
        })

        payslip_shrek = self._generate_payslip(date(2024, 1, 1), domain_test_structure_01, employee=self.shrek_emp)
        payslip_donkey = self._generate_payslip(date(2024, 1, 1), domain_test_structure_01, employee=self.donkey_emp)

        self._assert_rule_applied(payslip_shrek, 'DOMTRUE', 100.0)
        self._assert_rule_applied(payslip_shrek, 'DOMSHREK', 200.0)
        self._assert_rule_not_applied(payslip_shrek, 'DOMFALSE')

        self._assert_rule_applied(payslip_donkey, 'DOMTRUE', 100.0)
        self._assert_rule_not_applied(payslip_donkey, 'DOMSHREK')
        self._assert_rule_not_applied(payslip_donkey, 'DOMFALSE')

    def test_domain_02_dynamic_and_company_specific(self):
        domain_test_structure_02 = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for domain test 02',
            'type_id': self.structure_type.id,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Date Specific Domain Rule',
            'code': 'DOMDATE',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_02.id,
            'condition_select': 'domain',
            'condition_domain': '[("date_from", ">=", "2024-06-01")]',
            'amount_select': 'fix',
            'amount_fix': 150.0,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Company Specific Domain Rule',
            'code': 'DOMCOMP',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_02.id,
            'condition_select': 'domain',
            'condition_domain': '[("company_id.name", "=", "Donkey Comp")]',
            'amount_select': 'fix',
            'amount_fix': 250.0,
        })

        payslip_early = self._generate_payslip(date(2024, 5, 1), domain_test_structure_02, employee=self.shrek_emp)
        self._assert_rule_not_applied(payslip_early, 'DOMDATE')
        self._assert_rule_not_applied(payslip_early, 'DOMCOMP')

        payslip_early = self._generate_payslip(date(2024, 5, 1), domain_test_structure_02, employee=self.donkey_emp)
        self._assert_rule_not_applied(payslip_early, 'DOMDATE')
        self._assert_rule_applied(payslip_early, 'DOMCOMP', 250.00)

        payslip_june = self._generate_payslip(date(2024, 6, 1), domain_test_structure_02, employee=self.shrek_emp)
        self._assert_rule_applied(payslip_june, 'DOMDATE', 150.0)
        self._assert_rule_not_applied(payslip_june, 'DOMCOMP')

        payslip_june = self._generate_payslip(date(2024, 6, 1), domain_test_structure_02, employee=self.donkey_emp)
        self._assert_rule_applied(payslip_june, 'DOMDATE', 150.0)
        self._assert_rule_applied(payslip_june, 'DOMCOMP', 250.00)

    def test_domain_03_complex_and_dynamic_eval(self):
        domain_test_structure_03 = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for domain test 03',
            'type_id': self.structure_type.id,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Complex Domain Rule',
            'code': 'DOMCOMPX',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_03.id,
            'condition_select': 'domain',
            'condition_domain': "[('employee_id.name', 'in', ['Prince', 'Shrek']), ('date_from.year_number', '=', 2024)]",
            'amount_select': 'fix',
            'amount_fix': 300.0,
        })

        payslip_shrek_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_03, employee=self.shrek_emp)
        payslip_donkey_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_03, employee=self.donkey_emp)

        self._assert_rule_applied(payslip_shrek_2024, 'DOMCOMPX', 300.0)
        self._assert_rule_not_applied(payslip_donkey_2024, 'DOMCOMPX')

        payslip_shrek_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_03, employee=self.shrek_emp)
        payslip_donkey_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_03, employee=self.donkey_emp)

        self._assert_rule_not_applied(payslip_shrek_2025, 'DOMCOMPX')
        self._assert_rule_not_applied(payslip_donkey_2025, 'DOMCOMPX')

    def test_domain_04_complex_or_condition(self):
        domain_test_structure_04 = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for domain test 03',
            'type_id': self.structure_type.id,
        })

        self.env['hr.salary.rule'].create({
            'name': 'Complex Domain Rule',
            'code': 'DOMCOMPX',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_04.id,
            'condition_select': 'domain',
            'condition_domain': "['|', ('employee_id.name', 'in', ['Prince', 'Shrek']), ('date_from.year_number', '=', 2024)]",
            'amount_select': 'fix',
            'amount_fix': 300.0,
        })

        payslip_shrek_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_04, employee=self.shrek_emp)
        payslip_donkey_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_04, employee=self.donkey_emp)

        self._assert_rule_applied(payslip_shrek_2024, 'DOMCOMPX', 300.0)
        self._assert_rule_applied(payslip_donkey_2024, 'DOMCOMPX', 300.0)

        payslip_shrek_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_04, employee=self.shrek_emp)
        payslip_donkey_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_04, employee=self.donkey_emp)

        self._assert_rule_applied(payslip_shrek_2025, 'DOMCOMPX', 300.0)
        self._assert_rule_not_applied(payslip_donkey_2025, 'DOMCOMPX')

    def test_domain_05_employee_properties(self):
        domain_test_structure_05 = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for domain test 05',
            'type_id': self.structure_type.id,
        })

        self.shrek_emp.write({'employee_properties': [
            {
                'name': 'payroll_property',
                'type': 'char',
                'definition_changed': True,
                'value': 'Pomme'
            }
        ]})

        self.donkey_emp.write({'employee_properties': [
            {
                'name': 'payroll_property',
                'type': 'char',
                'definition_changed': True,
                'value': 'Poire'
            }
        ]})

        self.env['hr.salary.rule'].create({
            'name': 'Complex Domain Rule with property fields',
            'code': 'DOMCOMPX',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': domain_test_structure_05.id,
            'condition_select': 'domain',
            'condition_domain': "[('employee_id.employee_properties.payroll_property', '=', 'Pomme'), ('date_from.year_number', '=', 2024)]",
            'amount_select': 'fix',
            'amount_fix': 300.0,
        })

        payslip_shrek_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_05, employee=self.shrek_emp)
        payslip_donkey_2024 = self._generate_payslip(date(2024, 1, 1), domain_test_structure_05, employee=self.donkey_emp)

        self._assert_rule_applied(payslip_shrek_2024, 'DOMCOMPX', 300.0)
        self._assert_rule_not_applied(payslip_donkey_2024, 'DOMCOMPX')

        payslip_shrek_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_05, employee=self.shrek_emp)
        payslip_donkey_2025 = self._generate_payslip(date(2025, 1, 1), domain_test_structure_05, employee=self.donkey_emp)

        self._assert_rule_not_applied(payslip_shrek_2025, 'DOMCOMPX')
        self._assert_rule_not_applied(payslip_donkey_2025, 'DOMCOMPX')
