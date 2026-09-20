# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


class TestSdworxITExportCommon(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.it_company = cls.env['res.company'].create({
            'name': 'IT Company11',
            'country_id': cls.env.ref('base.it').id,
            'official_company_code': '000009',
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.it_company.ids))
        cls.richard_emp.write({
            'company_id': cls.it_company.id,
            'l10n_it_sdworx_code': '0000001',
        })
        cls.it_calendar_8h = cls.env['resource.calendar'].create({
            'name': 'IT 8h/day',
            'company_id': cls.it_company.id,
        })
        resource_calendar_attendance_values = []
        for dow in range(0, 5):
            resource_calendar_attendance_values.extend([{
                'name': 'Morning', 'dayofweek': str(dow), 'hour_from': 8.0, 'hour_to': 12.0, 'calendar_id': cls.it_calendar_8h.id,
            }, {
                'name': 'Afternoon', 'dayofweek': str(dow), 'hour_from': 13.0, 'hour_to': 16.0, 'calendar_id': cls.it_calendar_8h.id,
            }])
        cls.env['resource.calendar.attendance'].create(resource_calendar_attendance_values)

        cls.richard_emp.version_id.write({'resource_calendar_id': cls.it_calendar_8h.id})
        if cls.env.ref('base.module_hr_holidays').state == 'installed':
            cls.wet_legal_leave = cls.env['hr.work.entry.type'].create({
                'name': 'Legal Leave (SDWorx IT)',
                'code': 'IT_LEGAL_LEAVE',
                'l10n_it_sdworx_code': 'FER',
                'is_leave': True,
            })
            cls.leave_type_day_it = cls.env['hr.leave.type'].create({
                'name': 'IT Full-Day Leave',
                'company_id': cls.it_company.id,
                'requires_allocation': False,
                'request_unit': 'day',
                'leave_validation_type': 'no_validation',
                'work_entry_type_id': cls.wet_legal_leave.id,
            })
            cls.leave_type_half_day = cls.env['hr.leave.type'].create({
                'name': 'IT Half-Day Leave',
                'company_id': cls.it_company.id,
                'requires_allocation': False,
                'request_unit': 'half_day',
                'leave_validation_type': 'no_validation',
                'work_entry_type_id': cls.wet_legal_leave.id,
            })
