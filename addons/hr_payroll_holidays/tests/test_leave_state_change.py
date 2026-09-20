# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time

from odoo.tests.common import tagged
from odoo.addons.hr_payroll_holidays.tests.common import TestPayrollHolidaysBase


@tagged('post_install', '-at_install')
class TestLeaveStateChange(TestPayrollHolidaysBase):

    @freeze_time('2018-02-24 10:00:00')
    def test_leave_back_to_approval_leave_when_not_in_confirm_payslip(self):
        """
        ================================================================================================================
        | case 1: An approved leave can be moved back to confirm state if leave is not in done/paid payslip.           |
        | case 2: An approved leave can't be moved back to confirm state if leave is in done/paid payslip.             |
        ================================================================================================================
        """
        unpaid_leave_type = self.env['hr.leave.type'].create({
            'name': 'unpaid leave in days',
            'request_unit': 'day',
            'leave_validation_type': 'both',
            'time_type': 'leave',
            'requires_allocation': False,
            'work_entry_type_id': self.work_entry_type_unpaid.id,
        })
        unpaid_leave = self.env['hr.leave'].with_user(self.emp.user_id).create({
            'name': 'unpaid leave for 3 days',
            'employee_id': self.emp.id,
            'holiday_status_id': unpaid_leave_type.id,
            'request_date_from': '2018-02-23',
            'request_date_to': '2018-02-25',
        })

        unpaid_leave.with_user(self.joseph.id).action_approve()
        unpaid_leave.with_user(self.joseph.id).action_back_to_approval()
        self.assertEqual(
            unpaid_leave.state,
            "confirm",
            "Approved leave can be moved back to confirm state as long as not included in the done/paid payslip",
        )

        unpaid_leave.with_user(self.joseph).action_approve()
        payslip = self.env['hr.payslip'].create({
            'name': 'Donald Payslip',
            'employee_id': self.emp.id,
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        unpaid_leave.with_user(self.joseph).action_back_to_approval()
        self.assertEqual(
            unpaid_leave.state,
            "validate",
            "Approved leave can't be moved back to confirm state if included in done/paid payslip",
        )
