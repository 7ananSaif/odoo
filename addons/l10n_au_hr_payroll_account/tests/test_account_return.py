# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from .common import L10nPayrollAccountCommon
from .tools import mock_skip_stp_api_calls

from odoo.tests import tagged


@tagged("post_install", "post_install_l10n")
class TestAccountReturn(L10nPayrollAccountCommon):

    @mock_skip_stp_api_calls()
    def test_closing_entry_includes_salary_withholding_taxes(self):
        # We need to add some datas to the company to pass account return checks (required fields)
        self.company.write({
            'vat': '38528825722',
            'phone': '+61123456789',
            'email': 'test@test.test',
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': '2023-01-01',
            'date_end': '2023-01-31',
            'name': 'January Batch',
            'company_id': self.company.id,
        })

        payslip_run.generate_payslips(employee_ids=[self.employee_1.id, self.employee_2.id])
        payslip_run.action_validate()
        payslip_run.slip_ids.move_id.action_post()

        basic_return_type = self.env['account.return.type'].create({
            'name': 'VAT Return (Generic)',
            'report_id': self.env.ref('account.generic_tax_report').id,
            'deadline_start_date': '2023-01-01',
        })

        with freeze_time('2023-01-01'):
            tax_return = self.env['account.return'].create({
                'name': 'test tax return',
                'date_from': '2023-01-01',
                'date_to': '2023-01-31',
                'company_id': self.company.id,
                'type_id': basic_return_type.id,
            })

            with self.allow_pdf_render():
                tax_return.action_validate()

        self.assertRecordValues(tax_return.closing_move_ids.line_ids,
            [
                {'debit': 0.0, 'credit': 0.0},
                {'debit': 0.0, 'credit': 0.0},
                {'debit': 2557.0, 'credit': 0.0},  # Salary & Wages
                {'debit': 0.0, 'credit': 2557.0},  # Payable tax amount
            ]
        )
