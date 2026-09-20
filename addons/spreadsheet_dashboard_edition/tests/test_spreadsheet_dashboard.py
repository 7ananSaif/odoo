from odoo.tests import new_test_user

from odoo.addons.spreadsheet_dashboard.tests.common import DashboardTestCommon
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


class TestSpreadsheetDashboard(DashboardTestCommon, SpreadsheetTestCase):

    def test_is_from_data(self):
        dashboard = self.create_dashboard()
        xml_id = "spreadsheet_dashboard.external_id"
        self.env['ir.model.data'].create({
            'name': xml_id,
            'model': 'spreadsheet.dashboard',
            'res_id': dashboard.id,
        })
        self.assertFalse(dashboard.is_from_data)
        dashboard.sample_dashboard_file_path = 'spreadsheet_dashboard/sample_dashboard.json'
        self.assertTrue(dashboard.is_from_data)

    def test_dont_have_external_id(self):
        dashboard = self.create_dashboard()
        self.assertFalse(dashboard.is_from_data)

    def test_from_data_internal_user(self):
        dashboard = self.create_dashboard()
        user = new_test_user(self.env, login='raoul', groups='base.group_user')
        self.assertFalse(dashboard.with_user(user).is_from_data)
