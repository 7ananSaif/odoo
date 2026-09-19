# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'sepa_file')
class TestSEPAFile(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].iso20022_orgid_id = "123456789"

        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account') \
                                | cls.env.ref('hr.group_hr_user') \
                                | cls.env.ref('hr_payroll.group_hr_payroll_manager')

        cls.address_home = cls.env['res.partner'].create([{
            'name': "Test Employee",
            'company_id': cls.env.company.id,
        }])

        cls.bank_bnp = cls.env['res.bank'].create({
            'name': 'BNP Paribas',
            'bic': 'GEBABEBB'
        })
        cls.bank_ing = cls.env['res.bank'].create({
            'name': 'ING',
            'bic': 'BBRUBEBB'
        })

        cls.company_bank_account = cls.env['res.partner.bank'].create({
            'acc_type': "iban",
            'acc_number': "BE15001559627230",
            'bank_id': cls.bank_bnp.id,
            'partner_id': cls.env.company.partner_id.id,
            'company_id': cls.env.company.id,
        })

        cls.env['account.journal'].search([
            ('name', 'ilike', 'Bank'),
            ('company_id', '=', cls.env.company.id)
        ]).bank_account_id = cls.company_bank_account

        cls.bank_account = cls.env['res.partner.bank'].create({
            'acc_type': "iban",
            'acc_number': "BE53485391778653",
            'bank_id': cls.bank_ing.id,
            'partner_id': cls.address_home.id,
            'company_id': cls.env.company.id,
        })

        cls.employee = cls.env['hr.employee'].sudo().create({
            'name': "Test Employee",
            'work_contact_id': cls.address_home.id,
            'bank_account_ids': [Command.link(cls.bank_account.id)],
            'resource_calendar_id': cls.company.resource_calendar_id.id,
            'company_id': cls.env.company.id,
            'distance_home_work': 75,
            'private_country_id': cls.env.ref('base.be').id,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2018, 12, 31),
            'contract_date_start': date(2018, 12, 31),
            'wage': 2400,
            'wage_on_signature': 2400,
        }).sudo(False)

        cls.contract = cls.employee.version_id

    def test_sepa_file(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2023-01-01',
            'date_end': '2023-01-31',
            'name': 'January Batch',
            'company_id': self.company.id,
        })

        self.employee.action_toggle_primary_bank_account_trust()

        payslip_run.generate_payslips(employee_ids=[self.employee.id])
        payslip_run.action_validate()

        sepa_wizard = (self.env['hr.payroll.payment.report.wizard'].with_company(self.company).create({
            'payslip_ids': payslip_run.slip_ids.ids,
            'payslip_run_id': payslip_run.id,
            'export_format': 'sepa',
        }))
        sepa_wizard.generate_payment_report()

        sepa_file_content = base64.b64decode(payslip_run.payment_report).decode()
        self.assertTrue("<InstrPrty>HIGH</InstrPrty>" in sepa_file_content)
        self.assertTrue("<Cd>SALA</Cd>" in sepa_file_content)
        self.assertTrue(f"<Ustrd>/A/ {payslip_run.slip_ids.id}" in sepa_file_content)
        self.assertTrue(f"<Ustrd>{payslip_run.slip_ids.id}" not in sepa_file_content)
