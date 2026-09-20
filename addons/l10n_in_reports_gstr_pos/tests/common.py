# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from datetime import date

from odoo.addons.account.tests.common import TestTaxCommon
from odoo.addons.l10n_in_pos.tests.common import TestInPosBase
from odoo.tools import file_open

TEST_DATE = date(2023, 5, 20)
HSN_SCHEMA_TEST_DATE = date(2025, 5, 20)


class TestInGstrPosBase(TestInPosBase):
    """
    Base class for Indian GSTR and POS-related test cases.
    This class sets up the company, products, and configuration required
    for any test involving GSTR in a POS environment.
    """
    @classmethod
    @TestTaxCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data["company"].write({
            "l10n_in_gst_efiling_feature": True,
        })

        account_return_type = cls.env.ref('l10n_in_reports.in_gstr1_return_type')
        return_company = cls.company_data["company"]
        start_date, end_date = account_return_type._get_period_boundaries(return_company, TEST_DATE)
        cls.gstr1_report = cls.env['account.return'].create({
            'name': 'IN Tax Return',
            'type_id': account_return_type.id,
            'company_id': return_company.id,
            'date_from': start_date,
            'date_to': end_date
        })
        date_from, date_to = account_return_type._get_period_boundaries(return_company, HSN_SCHEMA_TEST_DATE)
        cls.gstr1_report_may_2025 = cls.env['account.return'].create({
            'name': 'GSTR-1 May 2025',
            'company_id': return_company.id,
            'type_id': account_return_type.id,
            'date_from': date_from,
            'date_to': date_to
        })

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
