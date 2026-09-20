# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.tests import tagged
from odoo.exceptions import UserError
from .common import TestPayrollCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPayrollScheduleChange(TestPayrollCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_change_schedule_without_start_date(self):
        """
        Test Case:
        Using the "Working Schedule Change" without a contract start date on the version will cause an UserError.
        """
        today = date.today()

        new_employee = self.create_employee({
            "name": "Test employee",
            "date_version": date(today.year - 2, 1, 1),
            "contract_date_start": False,
        })

        with self.assertRaises(UserError):
            new_employee.version_id.action_work_schedule_change_wizard()
