from odoo.tests import tagged
from .common import TestPayrollCommon
from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrPayrollEmployeeDepartureNotice(TestPayrollCommon):

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.leaving_type_fired = self.env['hr.departure.reason'].create({
            'name': 'Fired',
            'l10n_be_reason_code': 342,
        })

    def _create_wizard(self, use_seniority):
        return self.env['hr.payslip.employee.depature.notice'].create({
            'employee_id': self.employee_test.id,
            'start_notice_period': '2025-07-21',
            'leaving_type_id': self.leaving_type_fired.id,
            'salary_december_2013': 'superior',
            'use_seniority_at_hiring': use_seniority,
            'departure_description': 'Fired',
        })

    @freeze_time("2025-07-21")
    def test_notice_period_calculation_with_seniority_at_hiring(self):
        # Without using seniority at hiring
        wizard_no_seniority = self._create_wizard(use_seniority=False)
        wizard_no_seniority._notice_duration()
        weeks_after_2014_no = wizard_no_seniority.notice_duration_week_after_2014

        # With using seniority at hiring
        wizard_with_seniority = self._create_wizard(use_seniority=True)
        wizard_with_seniority._notice_duration()
        weeks_after_2014_yes = wizard_with_seniority.notice_duration_week_after_2014

        # Assertions (Employee contract_date_start is 01/01/2017)
        self.assertNotEqual(weeks_after_2014_yes, weeks_after_2014_no, "Notice duration should differ when using seniority at hiring")
        self.assertEqual(weeks_after_2014_yes, 36)
        self.assertEqual(weeks_after_2014_no, 27)
