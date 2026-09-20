# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon

from odoo.fields import Command


class TestL10NHkHrPayrollAccountCommon(TestPayslipValidationCommon):

    @classmethod
    def setup_armageddon_tax(cls, tax_name, company_data):
        # Hong Kong doesn't have any tax, so this methods will throw errors if we don't return None
        return None

    @classmethod
    @TestPayslipValidationCommon.setup_country('hk')
    def setUpClass(cls):
        super().setUpClass()

        payroll_manager = cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.env.user.group_ids |= payroll_manager

        cls.resource_calendar = cls.env['resource.calendar'].create({
            'name': "Test Calendar : 40 Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': 8.0,
            'tz': "Asia/Hong_Kong",
            'two_weeks_calendar': False,
            'hours_per_week': 40,
            'full_time_required_hours': 40,
            'attendance_ids': [
                (5, 0, 0),
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Saturday Morning', 'dayofweek': '5', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning', 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'name': 'Saturday Afternoon', 'dayofweek': '5', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon', 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'name': 'Sunday Morning', 'dayofweek': '6', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning', 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
                (0, 0, {'name': 'Sunday Afternoon', 'dayofweek': '6', 'hour_from': 13, 'hour_to': 17.0, 'day_period': 'afternoon', 'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_weekend').id}),
            ]
        })

        cls._setup_common(
            country=cls.env.ref('base.hk'),
            structure=cls.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.resource_calendar,
            contract_fields={
                'date_version': date(2023, 1, 1),
                'contract_date_start': date(2023, 1, 1),
                'wage': 20000.0,
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'marital': "single",
            }
        )

        # Set up a test MPF scheme,... and set it on the employee
        cls.mpf_scheme = cls.env['l10n_hk.mpf.scheme'].with_company(cls.env.company).create({
            'name': 'Mandatory Provident Fund Scheme',
            'registration_number': 'MT00298',
            'employer_account_number': '123456789012',
            'payroll_group_ids': [Command.create({
                'name': 'Staff - Monthly',
                'group_id': 'MLY',
                'contribution_frequency': 'monthly',
                'company_id': cls.env.company.id,
                'is_default': True,
            })],
        })
        cls.member_class = cls.env['l10n_hk.member.class'].with_company(cls.env.company).create({
            'name': 'GT1',
            'company_id': cls.env.company.id,
            'scheme_id': cls.mpf_scheme.id,
            'definition_of_service': 'date_of_employment',
            'contribution_type_ids': [Command.create({
                'contribution_type': 'employee',
                'contribution_option': 'top_up',
                'amount': 5,
                'definition_of_income': 'relevant_wages',
            }), Command.create({
                'contribution_type': 'employer',
                'contribution_option': 'match',
            })],
        })

        admin = cls.env['res.users'].search([('login', '=', 'admin')])
        admin.company_ids |= cls.env.company

        cls.env.user.tz = 'Asia/Hong_Kong'

    @classmethod
    def _setup_employee(cls, country, structure_type, resource_calendar, contract_fields=False, employee_fields=False):
        """ Simple helper to create a new employee. """
        work_contact = cls.env["res.partner"].create({
            "name": country.code.upper() + " Employee",
            "company_id": cls.env.company.id,
        })

        employee = (
            cls.env["hr.employee"]
            .sudo()
            .create(
                {
                    "name": country.code.upper() + " Employee",
                    "work_contact_id": work_contact.id,
                    "address_id": work_contact.id,
                    "resource_calendar_id": resource_calendar.id,
                    "company_id": cls.env.company.id,
                    "country_id": country.id,
                    "structure_type_id": structure_type.id,
                    "contract_date_start": date(2016, 1, 1),
                    "date_version": date(2016, 1, 1),
                    "wage": 1000.0,
                    **(employee_fields or {}),
                }
            )
            .sudo(False)
        )

        contract = employee.sudo().version_id
        if contract_fields:
            contract.write(contract_fields)

        return employee
