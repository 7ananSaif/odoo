# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


class TestSdworxExportCommon(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.belgian_company.write({
            'sdworx_code': '1111111',
        })

        cls.employee_georges.sdworx_code = '0000001'
        cls.employee_john.sdworx_code = '0000002'
        cls.employee_a.sdworx_code = '0000003'

        cls.work_entry_type_attendance = cls.env.ref('hr_work_entry.work_entry_type_attendance')
        cls.work_entry_type_attendance.sdworx_code = '7010'

        cls.work_entry_type_legal_leave = cls.env['hr.work.entry.type'].create({
            'name': 'Legal Leave (SDWorx Test)',
            'code': 'LEAVE999',
            'sdworx_code': 'T010',
        })
        cls.work_entry_type_hourly_leave = cls.env['hr.work.entry.type'].create({
            'name': 'Hourly Leave Extra Legal (SDWorx Test)',
            'code': 'LEAVEH999',
            'sdworx_code': '7282',
        })

        cls.leave_type_day = cls.holiday_leave_types[0]
        cls.leave_type_day.work_entry_type_id = cls.work_entry_type_legal_leave.id
        cls.leave_type_day.leave_validation_type = 'no_validation'

        cls.leave_type_half_day = cls.env['hr.leave.type'].create({
            'name': 'Half-Day Time Off',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'leave_validation_type': 'no_validation',
            'work_entry_type_id': cls.work_entry_type_legal_leave.id,
        })
        cls.leave_type_hour = cls.env['hr.leave.type'].create({
            'name': 'Hourly Time Off',
            'requires_allocation': False,
            'request_unit': 'hour',
            'leave_validation_type': 'no_validation',
            'work_entry_type_id': cls.work_entry_type_hourly_leave.id,
        })
