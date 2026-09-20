# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_right_to_legal_leaves')
class TestPayrollRightToLegalLeaves(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_edrs_activity_not_logged_without_notified_officers(self):
        """
        Create a time off request using a leave_type which doesn't have 'Notified Time Off Officers' and assert
        that eDRS activity isn't logged to the chatter.
        """
        leave_type_without_notified_officers = self.env['hr.leave.type'].create({
            'name': 'Leave Type Without Notified Officers',
            'requires_allocation': False,
            'employee_requests': True,
            'leave_validation_type': 'both',
            'responsible_ids': False,
            'request_unit': 'day'
        })
        leave_request = self.env['hr.leave'].create({
            'name': 'Leave 1 day',
            'employee_id': self.employee_georges.id,
            'holiday_status_id': leave_type_without_notified_officers.id,
            'request_date_from': '2024-10-31',
            'request_date_to': '2024-10-31',
        })
        leave_request.action_approve()
        activity = self.env['mail.activity'].search([
            ('res_id', '=', leave_request.id),
            ('res_model', '=', 'hr.leave'),
        ])
        self.assertFalse(activity)

    def test_sick_time_off_without_guaranteed_salary(self):
        """
        Test for long term sickness that the public holiday is overwritten with a sick time off (without guarantee salary),
        and that the time off is correctly linked to the work entry
        """
        sick_leave_type = self.env.ref('hr_holidays.leave_type_sick_time_off')
        sick_work_entry_type_without_salary = self.env.ref('hr_work_entry.l10n_be_work_entry_type_part_sick')
        sick_leave = self.env['hr.leave'].create({
            'name': 'Sick leave',
            'employee_id': self.employee_georges.id,
            'holiday_status_id': sick_leave_type.id,
            'request_date_from': datetime(2024, 1, 16),
            'request_date_to': datetime(2024, 9, 19),
        })
        sick_leave._action_validate()

        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2024, 9, 19, 8),
            'date_to': datetime(2024, 9, 19, 16),
            'calendar_id': self.employee_georges.resource_calendar_id.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday').id,
            'time_type': 'leave',
        })

        work_entries = self.employee_georges.generate_work_entries(date(2024, 1, 16), date(2024, 9, 19))
        public_holiday_date_work_entry = work_entries.filtered(lambda we: we.date == date(2024, 9, 19))
        self.assertEqual(public_holiday_date_work_entry.work_entry_type_id, sick_work_entry_type_without_salary)
        self.assertEqual(public_holiday_date_work_entry.leave_id, sick_leave)
