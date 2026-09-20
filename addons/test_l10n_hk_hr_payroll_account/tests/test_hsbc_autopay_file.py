# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import re

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHsbcAutoFile(TestL10NHkHrPayrollAccountCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.address_home = cls.env['res.partner'].create([{
            'name': "Test Employee",
            'company_id': cls.env.company.id,
        }])

        cls.bank_hsbc = cls.env['res.bank'].create({
            'name': 'HSBC',
            'bic': '004',
            'l10n_hk_bank_code': '004',
        })

        cls.company_bank_account = cls.env['res.partner.bank'].create({
            'acc_number': "848987654321",
            'bank_id': cls.bank_hsbc.id,
            'partner_id': cls.env.company.partner_id.id,
            'company_id': cls.env.company.id,
        })

        cls.bank_account = cls.env['res.partner.bank'].create({
            'acc_number': "1234567890",
            'bank_id': cls.bank_hsbc.id,
            'partner_id': cls.address_home.id,
            'company_id': cls.env.company.id,
            'acc_holder_name': "Test Employee",
        })

        cls.env.company.write({
            'l10n_hk_autopay': True,
            'l10n_hk_autopay_type': 'hsbcnet',
            'l10n_hk_autopay_partner_bank_id': cls.company_bank_account.id
        })

        cls._setup_common(
            country=cls.env.ref('base.hk'),
            structure=cls.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary'),
            structure_type=cls.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=cls.company.resource_calendar_id,
            contract_fields={
                'date_version': date(2024, 3, 1),
                'contract_date_start': date(2024, 3, 1),
                'wage': 33570.0,
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'marital': "single",
            }
        )
        cls.employee.write({
            'name': "Test Employee",
            'work_contact_id': cls.address_home.id,
            'bank_account_ids':  [Command.link(cls.bank_account.id)],
            'resource_calendar_id': cls.company.resource_calendar_id.id,
            'company_id': cls.env.company.id,
            'l10n_hk_autopay_account_type': 'bban',
            'identification_id': 'Z123456(7)'
        })

        public_holiday_to_create = [
            (datetime(2025, 5, 1), datetime(2025, 5, 1)),
            (datetime(2025, 5, 5), datetime(2025, 5, 5)),
            (datetime(2025, 5, 31), datetime(2025, 5, 31)),
        ]

        for date_from, date_to in public_holiday_to_create:
            cls.env['resource.calendar.leaves'].create([{
                'name': "Public Holiday (global)",
                'calendar_id': cls.company.resource_calendar_id.id,
                'company_id': cls.company.id,
                'date_from': date_from,
                'date_to': date_to,
                'resource_id': False,
                'time_type': "leave",
                'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_hk_work_entry_type_public_holiday').id
            }])

    def test_hsbc_autopay_file(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'name': "Test Payslip Run",
            'date_start': date(2025, 5, 1),
            'date_end': date(2025, 5, 31),
            'company_id': self.env.company.id,
        })
        hk_annual_leave_allocation = self.env['hr.leave.allocation'].create({
            'name': 'HK Annual Leave Allocation',
            'holiday_status_id': self.env.ref('hr_holidays.l10n_hk_leave_type_annual_leave').id,
            'number_of_days': 10,
            'employee_id': self.employee.id,
            'state': 'confirm',
            'date_from': '2025-01-01',
        })
        hk_annual_leave_allocation.action_approve()
        self._generate_leave(datetime(2025, 5, 8), datetime(2025, 5, 8), self.env.ref('hr_holidays.l10n_hk_leave_type_annual_leave'))
        payslip = self._generate_payslip(
            date(2025, 5, 1),
            date(2025, 5, 1) + relativedelta(day=31),
            input_line_ids=[(0, 0, {'input_type_id': self.env.ref('l10n_hk_hr_payroll.input_commission').id, 'amount': 1917.70})],
        )
        payslip.action_payslip_done()
        payslip_run.slip_ids = [payslip.id]
        payslip_run.action_validate()

        hsbc_autopay_wizard = (self.env['hr.payslip.run.hsbc.autopay.wizard'].with_context(active_id=payslip_run.id).with_company(self.company).create({
            'payment_date': date(2025, 5, 31),
            'payment_set_code': 'ABC',
            'file_name': 'Test_HSBC_Autopay_File.apc',
        }))
        hsbc_autopay_wizard.generate_hsbc_autopay_apc_file()

        hsbc_autopay_file_content = base64.b64decode(payslip_run.l10n_hk_autopay_export_first_batch).decode()
        content = re.split(r'\s{2,}', hsbc_autopay_file_content.strip())
        self.assertListEqual(content, [
            "PHFABC0",
            "20250531848987654321SAHKD",
            "HKD000000100000000003310480",
            "PD004BBAN1234567890",
            "00000000003310480Z1234567",
            "Test Employee",
        ])
