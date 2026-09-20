# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from freezegun import freeze_time
from odoo.addons.l10n_in_hr_payroll.tests.common import TestPayrollCommon
from odoo.tests import Form, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrContract(TestPayrollCommon):

    def test_contract_end_reminder_to_hr(self):
        """ Check reminder activity is set the for probation contract
        Test Case
        ---------
            1) Create contract
            2) Check the activity is activity schedule or not
            3) Now run cron
            4) Check the activity is activity schedule or not
        """
        user_admin_id = self.env.ref('base.user_admin').id

        contract = self.rahul_emp.create_version({
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end':  date(2020, 4, 30),
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
            'wage': 5000.0,
            'contract_type_id': self.env.ref('l10n_in_hr_payroll.l10n_in_contract_type_probation').id,
            'hr_responsible_id': user_admin_id,
        })
        with freeze_time("2020-05-07"):
            mail_activity = self.env['mail.activity'].search([('res_id', '=', contract.id), ('res_model', '=', 'hr.version')])
            self.assertFalse(mail_activity.exists(), "There should be no mail activity as contract is not ends on 2020-04-10")
            # run the cron
            self.env['hr.employee'].notify_expiring_contract_work_permit()
            mail_activity = self.env['mail.activity'].search([('res_id', '=', contract.id), ('res_model', '=', 'hr.version')])
            self.assertTrue(mail_activity.exists(), "There should be reminder activity as employee rahul's contract end today")

    def test_l10n_in_hr_version_computation(self):
        """ Test the computation of various fields in hr.version model """

        version = self.jethalal_emp.create_version({
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end':  date(2025, 4, 30),
            'name': 'Test Version',
            'wage': 50000.0,
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
            'contract_type_id': self.env.ref('l10n_in_hr_payroll.l10n_in_contract_type_probation').id,
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })

        with Form(version) as version_form:
            version_form.l10n_in_basic_percentage = 0.4
            version_form.l10n_in_hra_percentage = 0.5
            version_form.l10n_in_standard_allowance_percentage = 0.1
            version_form.l10n_in_performance_bonus_percentage = 0.05
            version_form.l10n_in_leave_travel_percentage = 0.05
            version_form.l10n_in_phone_subscription = 500
            version_form.l10n_in_internet_subscription = 300
            version_form.l10n_in_meal_voucher_amount = 1000
            version_form.l10n_in_company_transport = 800
            version_form.l10n_in_gratuity_percentage = 0.0481

        self.assertAlmostEqual(version.l10n_in_basic_salary_amount, 20000,
            msg="Basic salary amount should be 40% of wage")
        self.assertAlmostEqual(version.l10n_in_standard_allowance, 2000,
            msg="Standard allowance should be 10% of basic salary")
        self.assertAlmostEqual(version.l10n_in_hra, 10000, msg="HRA should be 50% of basic salary")
        self.assertAlmostEqual(version.l10n_in_performance_bonus, 1000,
            msg="Performance bonus should be 10% of basic salary")
        self.assertAlmostEqual(version.l10n_in_leave_travel_allowance, 1000, msg="LTA should be 5% of basic salary")
        self.assertAlmostEqual(version.l10n_in_fixed_allowance, 16000,
            msg="Fixed allowance should be wage minus sum of all allowances")
        self.assertAlmostEqual(
            version.l10n_in_gross_salary,
            20000 + 10000 + 2000 + 1000 + 1000 + 500 + 300 + 1000 + 800 + 16000,
            msg="Gross salary should be sum of all basic and allowances"
        )
        self.assertAlmostEqual(version.l10n_in_gratuity, 962.0,
            msg="Gratuity should be 4.81% of basic salary")

    def test_in_hr_version_percentage_computation(self):
        """ Test the computation of percentage fields in hr.version model """

        # TODO: fix this
        if self.env.ref('base.module_hr_contract_salary').state == 'installed':
            self.skipTest("Skip Test: Inconsistency with `hr_contract_salary` module")

        version = self.rahul_emp.create_version({
            'date_version': date(2025, 3, 1),
            'contract_date_start': date(2025, 3, 1),
            'contract_date_end':  date(2025, 6, 30),
            'name': 'Test Version',
            'wage': 50000.0,
            'l10n_in_basic_salary_amount': 20000,
            'l10n_in_hra': 10000,
            'l10n_in_standard_allowance': 1100,
            'l10n_in_performance_bonus': 1000,
            'l10n_in_leave_travel_allowance': 1000,
            'l10n_in_pf_employer_type': 'calculate',
            'l10n_in_pf_employee_type': 'calculate',
            'l10n_in_gratuity': 962,
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
            'contract_type_id': self.env.ref('l10n_in_hr_payroll.l10n_in_contract_type_probation').id,
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })

        with Form(version) as version_form:
            version_form.l10n_in_basic_salary_amount = 22000
            version_form.save()

        self.assertEqual(version.l10n_in_basic_percentage, 0.44,
            msg="Basic percentage should be 44% of updated wage")
        self.assertAlmostEqual(version.l10n_in_hra_percentage, 0.4, msg="HRA should be 40% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_standard_allowance_percentage, 0.05,
            msg="Standard allowance should be 5% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_performance_bonus_percentage, 0.3,
            msg="Performance bonus should be 30% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_leave_travel_percentage, 0.3,
            msg="LTA should be 30% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_fixed_allowance, 4900,
            msg="Fixed allowance should be wage minus sum of all allowances")
        self.assertAlmostEqual(version.l10n_in_pf_employee_amount, 2640,
            msg="PF employee amount should be 12% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_pf_employer_amount, 2640,
            msg="PF employer amount should be 12% of updated basic salary")
        self.assertAlmostEqual(version.l10n_in_gratuity_percentage, 0.0481,
            msg="Gratuity should be 4.81% of updated basic salary")

    def test_l10n_in_basic_percentage_computation(self):
        """ Test the computation of basic percentage fields in hr.version model in salary calculator for Indian company"""

        if 'hr_contract_salary' not in self.env["ir.module.module"]._installed():
            self.skipTest('hr_contract_salary is not installed')

        default_percentage = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_in_basic_percent', raise_if_not_found=False)
        offer = self.env['hr.contract.salary.offer'].create([{
            'monthly_wage': 0.0,
        }])

        offer.final_yearly_costs = 500000.0
        version = offer._get_version()
        version.company_id.country_code = 'IN'

        self.assertEqual(version.l10n_in_basic_percentage, default_percentage,
        msg="Default basic percentage should be 60%")
        self.assertEqual(version.l10n_in_basic_salary_amount, 25000.0)
