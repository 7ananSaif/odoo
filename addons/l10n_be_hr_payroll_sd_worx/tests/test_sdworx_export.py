# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import date

from odoo.tests import tagged
from .common import TestSdworxExportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSdworxExportLogic(TestSdworxExportCommon):

    def _generate_and_get_content(self, employees, month, year):
        export_form = self.env['l10n.be.hr.payroll.export.sdworx'].create({
            'reference_month': str(month),
            'reference_year': str(year),
        })

        start_date = export_form.period_start
        end_date = export_form.period_stop
        employees.generate_work_entries(start_date, end_date)
        contracts_by_employee = export_form._get_contracts_by_employee(employee_ids=employees.ids)
        create_lines = []
        for emp in employees:
            if emp in contracts_by_employee:
                create_lines.append((0, 0, {
                    'employee_id': emp.id,
                    'version_ids': [(6, 0, contracts_by_employee[emp].ids)]
                }))
        export_form.write({
            'eligible_employee_line_ids': [(5, 0, 0)] + create_lines
            })
        export_form.action_export_file()
        self.assertTrue(export_form.export_file, "The export file should have been generated.")
        return base64.b64decode(export_form.export_file).decode('utf-8')

    def test_export_full_day_leave(self):
        """
        Tests that a full day leave correctly replaces the attendance
        for that day in the export file.
        """

        self.env['hr.leave.allocation'].create({
            'name': 'Allocation for Georges',
            'holiday_status_id': self.leave_type_day.id,
            'number_of_days': 5,
            'employee_id': self.employee_georges.id,
            'state': 'confirm',
            'date_from': '2025-01-01',
        }).action_approve()
        leave_date = date(2025, 6, 9)
        self.env['hr.leave'].create({
            'name': 'Full Day Leave Test',
            'employee_id': self.employee_georges.id,
            'holiday_status_id': self.leave_type_day.id,
            'request_date_from': leave_date,
            'request_date_to': leave_date,
        }).action_approve()

        content = self._generate_and_get_content(self.employee_georges, 6, 2025)
        expected_leave_line = "11111110000001K20250609T0100760"
        self.assertIn(
            expected_leave_line, content, "The export file should contain the correct leave line for Georges."
        )
        self.assertNotIn("K202506097010", content), "The export file cannot contain attendance on full leave day"

    def test_export_with_multiple_employees_and_leaves(self):
        """
        Tests generating a single file for multiple employees who have a mix of
        full-day, half-day, and hourly leaves within the same period.
        """

        self.env['hr.leave'].create({
            'name': 'John Hourly',
            'employee_id': self.employee_john.id,
            'holiday_status_id': self.leave_type_hour.id,
            'request_date_from': date(2025, 7, 14),
            'request_date_to': date(2025, 7, 14),
            'request_unit_hours': True,
            'request_hour_from': 13.0,
            'request_hour_to': 16.0,
        })
        self.env['hr.leave.allocation'].create({
            'name': 'Allocation for Georges',
            'holiday_status_id': self.leave_type_day.id,
            'number_of_days': 5,
            'employee_id': self.employee_georges.id,
            'state': 'confirm',
            'date_from': '2025-01-01',
        }).action_approve()
        self.env['hr.leave'].create({
            'name': 'Georges Full Day',
            'employee_id': self.employee_georges.id,
            'holiday_status_id': self.leave_type_day.id,
            'request_date_from': date(2025, 7, 15),
            'request_date_to': date(2025, 7, 15),
        })
        self.env['hr.leave'].create({
            'name': 'Georges Half Day',
            'employee_id': self.employee_georges.id,
            'holiday_status_id': self.leave_type_half_day.id,
            'request_date_from': date(2025, 7, 16),
            'request_date_to': date(2025, 7, 16),
            'request_unit_half': True,
            'request_date_from_period': 'pm',
        })

        employees_to_test = self.employee_georges | self.employee_john
        content = self._generate_and_get_content(employees_to_test, 7, 2025)

        # --- Expected lines for Georges (ID 0000001) ---
        # Georges' calendar is Monday, Tuesday, Wednesday, Thursday [8-12, 13-16.6]
        # Full day leave on July 15th 7.6 hours
        georges_line_1 = "11111110000001K20250715T0100760"
        # Half-day leave (PM) on July 16th 3.6 hours
        georges_line_2 = "11111110000001K20250716T0100360"
        # Attendance (AM) on July 16th 4 hours
        georges_line_3 = "11111110000001K2025071670100400"

        # --- Expected lines for Employee John (ID 0000002) ---
        # John's calendar is Monday, Tuesday [8-12, 13-16.5], Wednesday [8-12]
        # AM attendance on July 14th 4.5 hours
        john_line_1 = "11111110000002K2025071470100450"
        # Hourly leave on July 14th 3 hours
        john_line_2 = "11111110000002K2025071472820300"

        self.assertIn(georges_line_1, content, "Georges' full day leave line is missing or incorrect.")
        self.assertIn(georges_line_2, content, "Georges' half-day leave line is missing or incorrect.")
        self.assertIn(georges_line_3, content, "Georges' half-day attendance is missing or incorrect.")

        self.assertIn(john_line_1, content, "John's attendance line is missing or incorrect.")
        self.assertIn(john_line_2, content, "John's hourly leave line is missing or incorrect.")
