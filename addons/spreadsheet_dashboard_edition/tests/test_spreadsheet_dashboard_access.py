import base64

from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user


class SpreadsheetDashboardAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env["res.groups"].create({"name": "test group"})
        cls.user = new_test_user(cls.env, login="Raoul")
        cls.user.group_ids |= cls.group

    def test_computed_name(self):
        group = self.env["spreadsheet.dashboard.group"].create(
            {"name": "a group"}
        )
        dashboard = self.env["spreadsheet.dashboard"].create(
            {
                "name": "My Dashboard",
                "dashboard_group_id": group.id,
                "spreadsheet_data": "{}",
            }
        )
        self.assertEqual(dashboard.spreadsheet_file_name, "My Dashboard.osheet.json")

    def test_update_data_reset_collaborative(self):
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
        dashboard.dispatch_spreadsheet_message({
            "type": "REMOTE_REVISION",
            "serverRevisionId": "rev-1-id",
            "nextRevisionId": "rev-2-id",
            "commands": [],
        })
        dashboard.dispatch_spreadsheet_message({
            "type": "SNAPSHOT",
            "serverRevisionId": "rev-2-id",
            "nextRevisionId": "rev-3-id",
            "data": {"revisionId": "rev-3-id"},
        })
        revisions = dashboard.with_context(active_test=False).spreadsheet_revision_ids
        self.assertEqual(len(revisions.exists()), 2)
        self.assertTrue(dashboard.spreadsheet_snapshot)
        dashboard.spreadsheet_data = '{ "version": 2 }'
        self.assertFalse(revisions.exists())
        self.assertFalse(dashboard.spreadsheet_snapshot)
