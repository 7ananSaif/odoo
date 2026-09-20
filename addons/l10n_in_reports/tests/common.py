import json

from odoo.addons.l10n_in.tests.common import L10nInTestInvoicingCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tools import file_open


class L10nInTestAccountReportsCommon(TestAccountReportsCommon, L10nInTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # === Companies === #
        cls.default_company.write({'l10n_in_gst_efiling_feature': True})
        cls.user.company_ids = [cls.default_company.id, cls.company_data_2['company'].id]

        # === Taxes === #
        cls.comp_igst_18 = cls.env['account.chart.template'].ref('igst_sale_18')

    @classmethod
    def _read_mock_json(self, filename):
        """
        Reads a JSON file using Odoo's file_open and returns the parsed data.

        :param filename: The name of the JSON file to read.
        :return: Parsed JSON data.
        """
        # Use file_open to open the file from the module's directory
        with file_open(f"{self.test_module}/tests/mock_jsons/{filename}", 'rb') as file:
            data = json.load(file)

        return data
