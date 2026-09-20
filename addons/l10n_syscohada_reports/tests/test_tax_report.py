
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class SyscohadaReportsTest(TestAccountReportsCommon):

    def test_syscohada_variants_availability(self):
        # Ensure syscohada variants are available from their root reports (using coa-children availability condition)
        self.company_data['company'].chart_template = 'bj'  # Benin is a child country of syscohada
        generic_balance_sheet = self.env.ref('account_reports.balance_sheet')
        syscohada_balance_sheet = self.env.ref('l10n_syscohada_reports.account_financial_report_syscohada_bilan')
        options = self._generate_options(generic_balance_sheet, '2022-02-01', '2022-02-28')
        variant_ids = {variant['id'] for variant in options['available_variants']}
        self.assertIn(syscohada_balance_sheet.id, variant_ids, "Syscohada Balance Sheet should be an available variant")
