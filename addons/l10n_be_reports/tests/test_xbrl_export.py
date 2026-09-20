from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestXBRLExports(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            'street': 'Rue du Paradis 200',
            'zip': '1000',
            'vat': 'BE0897223670',
            'l10n_be_company_type_id': cls.env['l10n_be.company.type'].search([], limit=1).id,
        })

    def _generate_file(self, report, options):
        """ Helper to generate the XBRL file with mocked data for the extra data method. If other
        modules override this method, we don't want to test their behavior here, just the XBRL export. """
        with patch.object(self.env.registry[report.custom_handler_model_name], '_get_extra_file_data', return_value={}):
            return self.env[report.custom_handler_model_name].generate_xbrl_file(options)

    @freeze_time('2025-06-30')
    def test_all_context_used(self):
        """ Test that all context tags are used in the XBRL export. """

        base_report = self.env.ref('account_reports.annual_statements')
        be_comp_report = next(variant for variant in base_report.variant_report_ids if variant.chart_template == 'be_comp')
        be_asso_report = next(variant for variant in base_report.variant_report_ids if variant.chart_template == 'be_asso')

        report_versions = [
            (be_comp_report, [('comp_acon', 'comp_a'), ('comp_fcon', 'comp_f'), ('comp_acap', 'comp_a'), ('comp_fcap', 'comp_f')]),
            (be_asso_report, [('asso_a', 'asso_a'), ('asso_f', 'asso_f')]),
        ]
        for be_report, versions in report_versions:
            for version in versions:

                for report in be_report.section_report_ids:
                    report.active = False

                self.env.ref(f'l10n_be_reports.account_financial_report_bs_{version[0]}').active = True
                self.env.ref(f'l10n_be_reports.account_financial_report_pl_{version[1]}').active = True

                options = self._generate_options(be_report, False, fields.Date.today())
                options['report_id'] = be_report.id
                options['last_deed_date'] = '2024-06-30'  # Required field for XBRL export
                xbrl_file = self._generate_file(base_report, options)

                self.assertTrue(xbrl_file)
                self.assertEqual(xbrl_file['file_type'], 'xml')

                file_content = self.get_xml_tree_from_string(xbrl_file['file_content'])

                # Check that the root element is 'xbrl'
                self.assertTrue(file_content.tag.endswith('xbrl'))

                context = file_content.findall('.//{*}context')
                context_refs = file_content.findall('.//*[@contextRef]')

                self.assertEqual(len(context), len(context_refs), f"Each contextRef should have a corresponding context element in XBRL template: {version}")

                # Check that each context id is unique
                context_ids = {c.attrib.get('id') for c in context}
                self.assertEqual(len(context), len(context_ids), f"Each context id should be unique in XBRL template: {version}")
                self.assertEqual(len(context_refs), len({c.attrib.get('contextRef') for c in context_refs}), f"Each contextRef should be unique in XBRL template: {version}")

                # Check that each contextRef matches an existing context id
                for value in context_refs:
                    self.assertIn(value.attrib.get('contextRef'), context_ids, f"contextRef should match an existing context id in XBRL template: {version}")

                # Check that required context tags are present
                expected_context_vars = {
                    'registration_number', 'date', 'start_period', 'end_period',
                    'company_name', 'company_type', 'company_street', 'company_house_number',
                    'company_postal_code', 'company_country', 'company_region', 'last_deed_date',
                }
                for var in expected_context_vars:
                    self.assertIn(var, context_ids, f"Context variable '{var}' is missing in XBRL template: {version}")

    def test_wrong_report_selection(self):
        """ Test that an error is raised when the selected reports do not match the XBRL export requirements. """

        base_report = self.env.ref('account_reports.annual_statements')
        be_report = next(variant for variant in base_report.variant_report_ids if variant.chart_template == 'be_comp')

        # Try to generate XBRL from non-Belgian report
        options = self._generate_options(base_report, False, fields.Date.today())
        with self.assertRaisesRegex(UserError, r"XBRL export is only applicable for Belgium reports. Please change to Belgium annual statement report."):
            self._generate_file(base_report, options)

        # Using Belgian report, select only one report instead of a pair of balance sheet and profit & loss
        be_report.section_report_ids.active = False
        self.env.ref('l10n_be_reports.account_financial_report_bs_comp_acon').active = True

        options = self._generate_options(be_report, False, fields.Date.today())
        options['report_id'] = be_report.id

        with self.assertRaisesRegex(UserError, r"Please add a single balance sheet and a single profit and loss report that have a matching \(Abbr or Full\) format for the XBRL export."):
            self._generate_file(base_report, options)

        # Now select a pair of reports with initial wrong selection
        self.env.ref('l10n_be_reports.account_financial_report_bs_comp_acap').active = True
        self.env.ref('l10n_be_reports.account_financial_report_pl_comp_a').active = True

        with self.assertRaisesRegex(UserError, r"Please add a single balance sheet and a single profit and loss report that have a matching \(Abbr or Full\) format for the XBRL export."):
            self._generate_file(base_report, options)

        # Now with a valid pair of reports
        be_report.section_report_ids.active = False
        self.env.ref('l10n_be_reports.account_financial_report_bs_comp_fcon').active = True
        self.env.ref('l10n_be_reports.account_financial_report_pl_comp_f').active = True

        xbrl_file = self._generate_file(base_report, options)
        self.assertTrue(xbrl_file)
        self.assertEqual(xbrl_file['file_type'], 'xml')

    def test_alphanumeric_zip_code(self):
        """
        Test that the Belgian region is correctly computed for a valid numeric ZIP code
        and that it is safely ignored for non-numeric ZIP codes.
        """
        self.company.l10n_be_region_id = False

        self.company.zip = 'R93R2R3'
        self.assertFalse(self.company.l10n_be_region_id)

        self.company.zip = '1000'
        self.assertTrue(self.company.l10n_be_region_id)
