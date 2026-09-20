from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import freeze_time
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@freeze_time('2024-01-01')
@tagged('post_install', '-at_install')
class TestKpiProvider(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company.write({
            'vat': '38972223422',
            'phone': '555-555-5555',
            'email': 'test@example.com'
        })
        cls.return_types = cls.env['account.return.type'].create([
            {'name': 'Return with a report without a root report',
             'report_id': cls.env.ref('account.generic_tax_report').id,
             'deadline_start_date': '2024-01-01'},
            {'name': 'Return with a root report',
             'report_id': cls.env.ref('account_reports.followup_report').id,
             'deadline_start_date': '2024-01-01'},
            {'name': 'Return without a report',
             'deadline_start_date': '2024-01-01'},
        ])

        def generate_all_returns(account_return_type, country_code, main_company, tax_unit=None):
            for return_type in cls.return_types:
                return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)

        with patch.object(cls.registry['account.return.type'], '_generate_all_returns', generate_all_returns):
            cls.env.company.account_opening_date = '2024-01-01'

    def test_kpi_summary(self):
        self.assertCountEqual(self.env['kpi.provider'].get_account_reports_kpi_summary(), [
            {'id': 'account_return.account_generic_tax_report',
             'name': 'Generic Tax report',
             'type': 'return_status',
             'value': 'to_do'},
            {'id': 'account_return.account_reports_partner_ledger_report',
             'name': 'Follow-Up Report',
             'type': 'return_status',
             'value': 'to_do'},
            {'id': 'account_return.return_without_a_report',
             'name': 'Return without a report',
             'type': 'return_status',
             'value': 'to_do'},
        ])
