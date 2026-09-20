from datetime import date

from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.hr_contract_salary.tests.test_employee_salary_configurator import (
    TestEmployeeSalaryConfigurator,
)


@tagged('-at_install', 'post_install', 'post_install_l10n', 'salary')
class TestEmployeeSalaryConfiguratorBelgium(TestEmployeeSalaryConfigurator):
    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

        cls.res_partner = cls.env['res.partner'].create(dict(
            name="Ahmed Abdelrazek",
            vat="BE0477472701",
            country_id=cls.env.ref('base.be').id,
        ))

        cls.bank_account = cls.env['res.partner.bank'].create({
            'acc_number': 'BE10 3631 0709 4104',
            'partner_id': cls.res_partner.id,
        })

        cls.employee_1.unlink()

        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Ahmed Abdelrazek',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
            'company_id': cls.company_id.id,
            'job_id': cls.job.id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'work_email': 'ahmed.abdelrazek@test_email.com',
            'bank_account_ids': cls.bank_account,
        })

    def test_employee_salary_configurator_flow(self):
        employee = self.env['hr.employee'].search([('name', 'ilike', 'Ahmed Abdelrazek')])
        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/", 'hr_contract_salary_employee_flow_tour', login='admin', timeout=350)
            self.assertEqual(employee.bank_account_ids.acc_holder_name, "Mohamed Dallash", "Account Holder name should have the same value as the one on the salary configurator")
