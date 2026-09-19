from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestAccountReturn(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_chart_template('nz')
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_return_type = cls.env.ref('l10n_nz_reports.nz_tax_return_type')

    def test_tax_return_start_date(self):
        self.tax_return_type.deadline_start_date = "2025-02-01"
        start_day, start_month = self.tax_return_type._get_start_date_elements(self.env.company)
        self.assertEqual(start_day, 1)
        self.assertEqual(start_month, 2)
