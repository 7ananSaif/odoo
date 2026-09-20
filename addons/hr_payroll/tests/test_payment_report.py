# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import csv
import io

from datetime import date
from odoo import Command, fields
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tools.misc import format_date


class TestHrPayslipPaymentReport(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_bank_account = cls.env['res.partner.bank'].create({
            'acc_number': "9876543210",
            'partner_id': cls.richard_emp.work_contact_id.id,
            'acc_type': 'bank',
            'allow_out_payment': True,
        })
        cls.richard_emp.bank_account_ids = [Command.link(cls.partner_bank_account.id)]
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': cls.richard_emp.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
        })

    def test_payslip_payment_report_fields_and_attachment(self):
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()

        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': [self.payslip.id],
            'export_format': 'csv',
        })
        wizard.generate_payment_report()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', '=', self.payslip.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertTrue(self.payslip.payment_report, "Payment report should be set initially.")
        self.assertTrue(self.payslip.payment_report_filename)
        self.assertTrue(self.payslip.payment_report_date)
        self.assertEqual(attachment_count, 1, "Attachment should exist before clearing.")

        self.payslip.action_payslip_draft()
        self.env.cr.flush()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip'),
            ('res_id', '=', self.payslip.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertFalse(self.payslip.payment_report, "Payment report should be cleared.")
        self.assertFalse(self.payslip.payment_report_filename, "Filename should be cleared.")
        self.assertFalse(self.payslip.payment_report_date, "Date should be cleared.")
        self.assertEqual(attachment_count, 0, "Attachment should be deleted after clearing.")


class TestHrPayrunPaymentReport(TestHrPayslipPaymentReport):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.payslip_run = cls.env['hr.payslip.run'].create({
            'name': 'Test Batch',
            'date_start': date(2025, 1, 1),
            'date_end': date(2025, 1, 31),
        })
        cls.payslip.payslip_run_id = cls.payslip_run

    def test_payrun_payment_report_fields_and_attachment(self):
        self.payslip_run.action_confirm()
        self.payslip_run.action_validate()

        self.payslip_run.action_payment_report()
        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', '=', self.payslip_run.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertTrue(self.payslip_run.payment_report, "Payrun payment report should be set initially.")
        self.assertTrue(self.payslip_run.payment_report_filename)
        self.assertTrue(self.payslip_run.payment_report_format)
        self.assertTrue(self.payslip_run.payment_report_date)
        self.assertEqual(attachment_count, 1, "Payrun report attachment should exist before clearing.")

        self.payslip_run.action_draft()
        self.env.cr.flush()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', '=', self.payslip_run.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertFalse(self.payslip_run.payment_report, "Payrun payment report should be cleared.")
        self.assertFalse(self.payslip_run.payment_report_filename, "Payment report filename should be cleared.")
        self.assertFalse(self.payslip_run.payment_report_format, "Payment report file format should be cleared")
        self.assertFalse(self.payslip_run.payment_report_date, "Payment report date should be cleared.")
        self.assertEqual(attachment_count, 0, "Payrun report attachment should be deleted after clearing.")

    def test_payrun_payment_report_with_multiple_payslips(self):
        self.payslip.compute_sheet()
        self.payslip.action_payslip_done()

        test_structure = self.env['hr.payroll.structure'].create({
            'name': 'Test Salary Structure',
            'type_id': self.structure_type.id,
        })

        net_salary_rule = test_structure.rule_ids.filtered(lambda r: r.code == "NET")
        net_salary_rule.write({
            'amount_select': 'fix',
            'amount_fix': 0.0,

        })

        self.env['hr.payslip'].create({
            'name': 'Test Payslip with 0.0 net salary',
            'employee_id': self.richard_emp.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
            'payslip_run_id': self.payslip_run.id,
            'struct_id': test_structure.id,
        })

        self.payslip_run.action_confirm()
        self.payslip_run.action_validate()

        wizard = self.env['hr.payroll.payment.report.wizard'].create({
            'payslip_ids': self.payslip_run.slip_ids.ids,
            'payslip_run_id': self.payslip_run.id,
            'export_format': 'csv',
        })
        wizard.generate_payment_report()

        attachment_count = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'hr.payslip.run'),
            ('res_id', '=', self.payslip_run.id),
            ('res_field', '=', 'payment_report'),
        ])

        self.assertTrue(self.payslip_run.payment_report, "Payrun payment report should be set.")
        self.assertTrue(self.payslip_run.payment_report_filename)
        self.assertTrue(self.payslip_run.payment_report_format)
        self.assertTrue(self.payslip_run.payment_report_date)
        self.assertEqual(attachment_count, 1, "Payrun report attachment should exist.")

        csv_data = base64.b64decode(self.payslip_run.payment_report)
        content = csv_data.decode('utf-8')
        reader = csv.reader(io.StringIO(content), delimiter=',')

        expected_values = [
            # Header row
            [
                'Sequence', 'Payment Date', 'Report Date', 'Payslip Period',
                'Employee name', 'Bank account', 'BIC', 'Amount to pay'
            ],
            # First data row
            [
                '1',
                format_date(wizard.env, wizard.effective_date),
                format_date(wizard.env, fields.Date.today()),
                format_date(wizard.env, self.payslip.date_from) + ' - ' + format_date(wizard.env, self.payslip.date_to),
                'Richard',
                '9876543210',
                '',
                '$ 7,205.42',
            ],
        ]

        for idx, content in enumerate(reader):
            self.assertSequenceEqual(expected_values[idx], content)
