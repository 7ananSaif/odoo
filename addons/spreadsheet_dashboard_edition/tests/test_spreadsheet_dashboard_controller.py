import json

from odoo import Command
from odoo.tools import file_open
from odoo.tests.common import HttpCase
from odoo.addons.spreadsheet_dashboard.tests.common import DashboardTestCommon
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


class TestSpreadsheetDashboard(DashboardTestCommon, SpreadsheetTestCase, HttpCase):

    def test_join_new_dashboard_user(self):
        self.authenticate(self.user.login, self.user.password)
        dashboard_group = self.env["spreadsheet.dashboard.group"].create({
            "name": "Dashboard group"
        })
        dashboard = self.env["spreadsheet.dashboard"].create(
            {
                "name": "a dashboard",
                "spreadsheet_data": "{}",
                "group_ids": [Command.set(self.group.ids)],
                "dashboard_group_id": dashboard_group.id,
            }
        )
        # only read access, no one ever joined this dashboard
        response = self.url_open('/spreadsheet/data/spreadsheet.dashboard/%s' % dashboard.id)
        result = response.json()
        self.assertEqual(result["data"], {})
        self.assertEqual(result["isReadonly"], True)

    def test_join_published(self):
        dashboard = self.create_dashboard().with_user(self.user)
        self.authenticate(self.user.login, self.user.password)
        response = self.url_open('/spreadsheet/data/spreadsheet.dashboard/%s' % dashboard.id)
        self.assertTrue(response.json()["is_published"])
        dashboard.sudo().is_published = False
        response = self.url_open('/spreadsheet/data/spreadsheet.dashboard/%s' % dashboard.id)
        self.assertFalse(response.json()["is_published"])

    def test_load_with_user_locale(self):
        dashboard = self.create_dashboard().with_user(self.user)
        self.authenticate(self.user.login, self.user.password)
        self.user.lang = "en_US"
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        snapshot = data["snapshot"]
        snapshot_locale = snapshot["settings"]["locale"]
        self.assertEqual(snapshot_locale["code"], "en_US")
        revisions = data["revisions"]
        self.assertEqual(len(revisions), 1)
        locale_revision = revisions[-1]
        self.assertEqual(locale_revision["serverRevisionId"], snapshot["revisionId"])
        self.assertEqual(locale_revision["commands"][0]["type"], "UPDATE_LOCALE")
        self.assertEqual(locale_revision["commands"][0]["locale"]["code"], "en_US")
        self.assertEqual(locale_revision["commands"][0]["locale"]["weekStart"], 7)

        self.env.ref("base.lang_fr").active = True
        self.user.lang = "fr_FR"

        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        snapshot = data["snapshot"]
        snapshot_locale = snapshot["settings"]["locale"]
        self.assertEqual(
            snapshot_locale["code"], "en_US", "snapshot locale is not changed"
        )
        revisions = data["revisions"]
        locale_revision = revisions[-1]
        self.assertEqual(locale_revision["serverRevisionId"], snapshot["revisionId"])
        self.assertEqual(locale_revision["commands"][0]["type"], "UPDATE_LOCALE")
        self.assertEqual(locale_revision["commands"][0]["locale"]["code"], "fr_FR")
        self.assertEqual(locale_revision["commands"][0]["locale"]["weekStart"], 1)

    def test_load_with_company_currency(self):
        self.authenticate(self.user.login, self.user.password)
        dashboard = self.create_dashboard().with_user(self.user)
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        self.assertEqual(
            data["default_currency"],
            self.env["res.currency"].get_company_currency_for_spreadsheet()
        )

    def test_load_with_user_locale_existing_revisions(self):
        self.authenticate(self.user.login, self.user.password)
        dashboard = self.create_dashboard()
        dashboard.dispatch_spreadsheet_message(self.new_revision_data(dashboard))

        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        revisions = data["revisions"]
        self.assertEqual(len(revisions), 2)
        self.assertEqual(
            revisions[-1]["serverRevisionId"],
            revisions[-2]["nextRevisionId"],
            "revisions ids are chained",
        )

    def test_translation_namespace(self):
        dashboard = self.create_dashboard()
        self.env['ir.model.data'].sudo().create({
            'name': 'test_translation_namespace',
            'module': 'spreadsheet_dashboard_edition',
            'res_id': dashboard.id,
            'model': dashboard._name,
        })
        self.authenticate(self.user.login, self.user.password)
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        self.assertEqual(data["translation_namespace"], "spreadsheet_dashboard_edition")

    def test_load_sample_dashboard(self):
        self.authenticate(self.user.login, self.user.password)
        sample_dashboard_path = "spreadsheet_dashboard_edition/tests/data/sample_dashboard.json"

        def get_sample_data():
            with file_open(sample_dashboard_path, 'rb') as f:
                return json.load(f)
        dashboard = self.create_dashboard()
        dashboard.main_data_model_ids = [(4, self.env.ref("base.model_res_bank").id)]
        dashboard.sample_dashboard_file_path = sample_dashboard_path

        # when no records are available for the main data model and no revisions, the sample data is loaded
        self.env["res.bank"].search([]).action_archive()
        self.env["spreadsheet.revision"].search([]).unlink()
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        self.assertTrue(data["is_sample"])
        self.assertEqual(data["snapshot"], get_sample_data())

        # when there are revisions, the sample data is not loaded
        dashboard.dispatch_spreadsheet_message(self.new_revision_data(dashboard))
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        self.assertFalse(data.get("is_sample"))
        self.assertNotEqual(data["snapshot"], get_sample_data())

        # when no revisions, but we have records for the main data model, the sample data is not loaded
        self.env["spreadsheet.revision"].search([]).unlink()
        self.env["res.bank"].create({"name": "My bank"})
        response = self.url_open('/spreadsheet/dashboard/data/%s' % dashboard.id)
        data = response.json()
        self.assertFalse(data.get("is_sample"))
        self.assertNotEqual(data["snapshot"], get_sample_data())

    def test_get_selector_spreadsheet_models(self):
        result = self.env["spreadsheet.mixin"].with_user(self.user).get_selector_spreadsheet_models()
        self.assertFalse(any(r["model"] == "spreadsheet.dashboard" for r in result))

        self.user.group_ids |= self.env.ref("spreadsheet_dashboard.group_dashboard_manager")
        result = self.env["spreadsheet.mixin"].with_user(self.user).get_selector_spreadsheet_models()
        self.assertTrue(any(r["model"] == "spreadsheet.dashboard" for r in result))
