# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from freezegun import freeze_time
import psycopg2
import json
import copy as COPY
from odoo.tools import mute_logger

from odoo.exceptions import UserError
from odoo.tests.common import new_test_user
from odoo.addons.spreadsheet_edition.tests.spreadsheet_test_case import SpreadsheetTestCase


def add_thread_command(x):
    return {
        "type": "ADD_COMMENT_THREAD",
        "sheetId": "sh1",
        "col": 0,
        "row": 1,
        "threadId": x,
    }

class SpreadsheetMixinTest(SpreadsheetTestCase):

    def test_copy_revisions(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy()
        self.assertEqual(
            copy.spreadsheet_revision_ids.commands,
            spreadsheet.spreadsheet_revision_ids.commands,
        )

    def test_copy_parent_revisions(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy()
        revisions = copy.spreadsheet_revision_ids
        self.assertEqual(len(revisions), 3)
        self.assertEqual(
            revisions[2].parent_revision_id,
            revisions[1],
        )
        self.assertEqual(
            revisions[1].parent_revision_id,
            revisions[0],
        )
        self.assertFalse(revisions[0].parent_revision_id)

    def test_dont_copy_revisions_if_provided(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy({"spreadsheet_revision_ids": []})
        self.assertFalse(copy.spreadsheet_revision_ids)

    def test_dont_copy_revisions_if_data_changes(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.copy({"spreadsheet_data": "{}"})
        self.assertFalse(copy.spreadsheet_revision_ids)

    def test_copy_filters_out_comments(self):
        base_data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
            "revisionId": "revision-id"
        }
        spreadsheet = self.env["spreadsheet.test"].create({"spreadsheet_data": json.dumps(base_data)})

        spreadsheet._dispatch_command(add_thread_command(2))
        snapshot_data = COPY.deepcopy(base_data)
        snapshot_data["revisionId"] = "snapshot-revision-id"
        snapshot_data["sheets"][0]["comments"][0]["A2"] = {"threadId": 1, "isResolved": False}

        self.snapshot(spreadsheet, spreadsheet.current_revision_uuid, "snapshot-revision-id", snapshot_data)
        spreadsheet._dispatch_command(add_thread_command(3))

        copy = spreadsheet.copy().with_context(active_test=False)  # get all the archived revisions

        copied_data = json.loads(copy.spreadsheet_data)
        copied_snapshot = json.loads(copy._get_spreadsheet_serialized_snapshot())  # snapshot
        copied_revision_before = json.loads(copy.spreadsheet_revision_ids[0].commands)  # revision before snapshot
        copied_revision_after = json.loads(copy.spreadsheet_revision_ids[2].commands)  # revision after snapshot

        self.assertEqual(copied_data["sheets"][0]["comments"], {})
        self.assertEqual(copied_snapshot["sheets"][0]["comments"], {})
        self.assertEqual(copied_revision_before["commands"], [])
        self.assertEqual(copied_revision_after["commands"], [])

    def test_fork_history_filters_out_comments(self):
        base_data = {
            "sheets": [{
                "comments": [
                    {"A1": {"threadId": 1, "isResolved": False}}
                ]
            }],
            "revisionId": "revision-id"
        }
        spreadsheet = self.env["spreadsheet.test"].create({"spreadsheet_data": json.dumps(base_data)})

        spreadsheet._dispatch_command(add_thread_command(2))
        snapshot_data = COPY.deepcopy(base_data)
        snapshot_data["revisionId"] = "snapshot-revision-id"
        snapshot_data["sheets"][0]["comments"][0]["A2"] = {"threadId": 1, "isResolved": False}

        self.snapshot(spreadsheet, spreadsheet.current_revision_uuid, "snapshot-revision-id", snapshot_data)
        spreadsheet._dispatch_command(add_thread_command(3))

        action = spreadsheet.fork_history(spreadsheet.spreadsheet_revision_ids[-1].id, snapshot_data)
        fork_id = action["params"]["spreadsheet_id"]
        fork = self.env["spreadsheet.test"].browse(fork_id).with_context(active_test=False)  # get all the archived revisions

        copied_data = json.loads(fork.spreadsheet_data)
        copied_snapshot = json.loads(fork._get_spreadsheet_serialized_snapshot())  # snapshot
        copied_revision_before = json.loads(fork.spreadsheet_revision_ids[0].commands)  # revision before snapshot
        copied_revision_after = json.loads(fork.spreadsheet_revision_ids[2].commands)  # revision after snapshot

        self.assertEqual(copied_data["sheets"][0]["comments"], {})
        self.assertEqual(copied_snapshot["sheets"][0]["comments"], {})
        self.assertEqual(copied_revision_before["commands"], [])
        self.assertEqual(copied_revision_after["commands"], [])


    def test_reset_spreadsheet_data(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        # one revision before the snapshot (it's archived by the snapshot)
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid, "snapshot-revision-id", {"sheets": [], "revisionId": "snapshot-revision-id"},
        )
        # one revision after the snapshot
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.spreadsheet_data = r"{}"
        self.assertFalse(spreadsheet.spreadsheet_snapshot)
        self.assertFalse(
            spreadsheet.with_context(active_test=True).spreadsheet_revision_ids,
        )

    def test_cannot_dispatch_with_invalid_parent_revision(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        revision_payload = self.new_revision_data(spreadsheet)
        is_accepted = spreadsheet.dispatch_spreadsheet_message(revision_payload)
        self.assertTrue(is_accepted, "the first revision should be accepted")

        revision_payload = self.new_revision_data(spreadsheet, serverRevisionId="something")
        is_accepted = spreadsheet.dispatch_spreadsheet_message(revision_payload)
        self.assertFalse(is_accepted)

    def test_cannot_delete_revision_in_a_chain(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revision = spreadsheet.spreadsheet_revision_ids[1]
        with self.assertRaises(psycopg2.errors.UniqueViolation), mute_logger("odoo.sql_db"):
            revision.unlink()

    def test_save_spreadsheet_snapshot(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        current_revision_uuid = spreadsheet.current_revision_uuid
        snapshot = {"sheets": [], "revisionId": spreadsheet.current_revision_uuid}
        spreadsheet.save_spreadsheet_snapshot(snapshot)
        self.assertNotEqual(spreadsheet.current_revision_uuid, current_revision_uuid)
        self.assertEqual(
            json.loads(spreadsheet._get_spreadsheet_serialized_snapshot()),
            dict(snapshot, revisionId=spreadsheet.current_revision_uuid),
        )

    def test_save_spreadsheet_snapshot_with_invalid_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        snapshot = {"sheets": [], "revisionId": spreadsheet.current_revision_uuid}

        # one revision is saved in the meantime (concurrently)
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))

        with self.assertRaises(UserError):
            spreadsheet.save_spreadsheet_snapshot(snapshot)

    def test_fork_history(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        rev1 = spreadsheet.spreadsheet_revision_ids[0]
        action = spreadsheet.fork_history(rev1.id, {"test": "snapshot"})
        self.assertTrue(isinstance(action, dict))

        copy_id = action["params"]["spreadsheet_id"]
        spreadsheet_copy = self.env["spreadsheet.test"].browse(copy_id)
        self.assertTrue(spreadsheet_copy.exists())
        fork_revision = spreadsheet_copy.with_context(active_test=False).spreadsheet_revision_ids
        self.assertEqual(len(fork_revision), 1)
        self.assertEqual(fork_revision.commands, rev1.commands)
        self.assertEqual(fork_revision.active, False)

    def test_fork_history_before_snapshot(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            "snapshot-revision-id",
             {"sheets": [], "revisionId": "snapshot-revision-id"}
        )
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        rev1 = spreadsheet.with_context(active_test=False).spreadsheet_revision_ids[0]
        fork_snapshot = {"test": "snapshot"}
        action = spreadsheet.fork_history(rev1.id, fork_snapshot)
        fork_id = action["params"]["spreadsheet_id"]
        spreadsheet_fork = self.env["spreadsheet.test"].browse(fork_id)
        self.assertEqual(json.loads(spreadsheet_fork._get_spreadsheet_serialized_snapshot()), fork_snapshot)
        self.assertEqual(
            spreadsheet_fork.with_context(active_test=False).spreadsheet_revision_ids.active,
            False
        )

    def test_restore_version(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revisions = spreadsheet.spreadsheet_revision_ids
        rev1 = revisions[0]
        rev2 = revisions[1]

        spreadsheet.restore_spreadsheet_version(
            rev1.id,
            {"test": "snapshot", "revisionId": rev1.revision_uuid}
        )
        self.assertFalse(rev1.active)
        self.assertFalse(rev2.exists())

        self.assertEqual(
            json.loads(spreadsheet._get_spreadsheet_serialized_snapshot()),
            {"test": "snapshot", "revisionId": spreadsheet.current_revision_uuid}
        )

    def test_restore_version_before_snapshot(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            "snapshot-revision-id",
            {"sheets": [], "revisionId": "snapshot-revision-id"},
        )
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))

        revisions = spreadsheet.with_context(active_test=False).spreadsheet_revision_ids
        rev1 = revisions[0]
        snapshot_rev = revisions[1]
        rev3 = revisions[2]

        spreadsheet.restore_spreadsheet_version(
            rev1.id,
            {"test": "snapshot", "revisionId": rev1.revision_uuid}
        )
        self.assertFalse(rev1.active)
        self.assertFalse((snapshot_rev | rev3).exists())

    def test_restore_version_as_base_user(self):
        user = new_test_user(self.env, login="test", groups="base.group_user")
        spreadsheet = self.env["spreadsheet.test"].with_user(user).create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revisions = spreadsheet.sudo().spreadsheet_revision_ids
        rev1 = revisions[0]
        rev2 = revisions[1]

        spreadsheet.restore_spreadsheet_version(
            rev1.id,
            {"test": "snapshot", "revisionId": rev1.revision_uuid}
        )
        self.assertFalse(rev1.active)
        self.assertFalse(rev2.exists())

        self.assertEqual(
            json.loads(spreadsheet._get_spreadsheet_serialized_snapshot()),
            {"test": "snapshot", "revisionId": spreadsheet.current_revision_uuid}
        )

    def test_rename_revision(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        revision = spreadsheet.spreadsheet_revision_ids[0]
        self.assertEqual(revision.name, False)

        spreadsheet.rename_revision(revision.id, "new revision name")
        self.assertEqual(revision.name, "new revision name")

    def test_get_spreadsheet_history(self):
        with freeze_time("2020-02-02"):
            spreadsheet = self.env["spreadsheet.test"].create({})
            spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            self.snapshot(
                spreadsheet,
                spreadsheet.current_revision_uuid, "snapshot-revision-id", {"sheets": [], "revisionId": "snapshot-revision-id"},
            )
            spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        user = spreadsheet.create_uid
        data = spreadsheet.get_spreadsheet_history()
        revisions = data["revisions"]
        self.assertEqual(len(revisions), 3)
        for revision in revisions:
            self.assertEqual(revision["timestamp"], datetime(2020, 2, 2, 0, 0, 0))
            self.assertEqual(revision["user"], (user.id, user.name))

        # from snapshot
        data = spreadsheet.get_spreadsheet_history(True)
        revisions = data["revisions"]
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0]["timestamp"], datetime(2020, 2, 2, 0, 0, 0))
        self.assertEqual(revisions[0]["user"], (user.id, user.name))

    def test_currency_passed_to_spreadsheet_history(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        company_eur = self.env["res.company"].create({"currency_id": self.env.ref("base.EUR").id, "name": "EUR"})
        company_gbp = self.env["res.company"].create({"currency_id": self.env.ref("base.GBP").id, "name": "GBP"})

        data = spreadsheet.with_company(company_eur).get_spreadsheet_history()
        self.assertEqual(data["default_currency"]["code"], "EUR")
        self.assertEqual(data["default_currency"]["symbol"], "€")

        data = spreadsheet.with_company(company_gbp).get_spreadsheet_history()
        self.assertEqual(data["default_currency"]["code"], "GBP")
        self.assertEqual(data["default_currency"]["symbol"], "£")

    def test_get_spreadsheet_base_user_access_right_history(self):
        user = new_test_user(self.env, login="test", groups="base.group_user")
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.invalidate_recordset()
        data = spreadsheet.with_user(user).get_spreadsheet_history()
        self.assertEqual(len(data["revisions"]), 1)

    def test_empty_spreadsheet_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        self.assertEqual(spreadsheet.current_revision_uuid, "START_REVISION")
        self.assertEqual(
            spreadsheet.with_context(bin_size=True).current_revision_uuid,
            "START_REVISION"
        )

    def test_no_data_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        spreadsheet.spreadsheet_snapshot = False
        spreadsheet.spreadsheet_data = False
        self.assertEqual(spreadsheet.current_revision_uuid, "START_REVISION")

    def test_last_revision_is_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})

        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet.dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

        # dispatch new revision on top
        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet.dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

    def test_snapshotted_server_revision_id(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        snapshot_revision_id = "snapshot-id"
        self.snapshot(
            spreadsheet,
            spreadsheet.current_revision_uuid,
            snapshot_revision_id,
            {"revisionId": snapshot_revision_id},
        )
        self.assertEqual(spreadsheet.current_revision_uuid, snapshot_revision_id)
        self.assertEqual(
            spreadsheet.with_context(bin_size=True).current_revision_uuid,
            snapshot_revision_id
        )

        # dispatch revision after snapshot
        revision_data = self.new_revision_data(spreadsheet)
        next_revision_id = revision_data["nextRevisionId"]
        spreadsheet.dispatch_spreadsheet_message(revision_data)
        self.assertEqual(spreadsheet.current_revision_uuid, next_revision_id)

    def test_get_spreadsheets(self):
        spreadsheet = self.env["spreadsheet.test"].create({})
        self.assertEqual(
            self.env["spreadsheet.test"].get_spreadsheets(),
            {
                "records": [{
                    "id": spreadsheet.id,
                    "display_name": spreadsheet.display_name,
                    "display_thumbnail": False
                }],
                "total": 1,
            }
        )

    def test_get_spreadsheets_limit(self):
        self.env["spreadsheet.test"].create({})
        self.env["spreadsheet.test"].create({})
        result = self.env["spreadsheet.test"].get_spreadsheets([], limit=1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["total"], 2)

    def test_get_spreadsheets_domain(self):
        first = self.env["spreadsheet.test"].create({})
        self.env["spreadsheet.test"].create({})
        result = self.env["spreadsheet.test"].get_spreadsheets([("id", "=", first.id)], limit=1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["id"], first.id)
        self.assertEqual(result["total"], 1)

    def test_get_selector_spreadsheet_models(self):
        result = self.env["spreadsheet.mixin"].get_selector_spreadsheet_models()
        self.assertTrue(any(r["model"] == "spreadsheet.test" for r in result))

    def test_action_open_new_spreadsheet(self):
        action = self.env["spreadsheet.test"].action_open_new_spreadsheet()
        spreadsheet = self.env["spreadsheet.test"].browse(action["params"]["spreadsheet_id"])
        self.assertTrue(spreadsheet.exists())

    def test_keep_original_spreadsheet_author_with_multiple_users(self):
        test_user_1 = new_test_user(self.env, login="test_user_1")
        test_user_2 = new_test_user(self.env, login="test_user_2")
        test_user_3 = new_test_user(self.env, login="test_user_3")
        spreadsheet = self.env["spreadsheet.test"].with_user(test_user_1).create({})
        spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.with_user(test_user_2).dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        spreadsheet.with_user(test_user_3).dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        copy = spreadsheet.with_user(self.env.ref("base.user_admin")).copy()
        revisions = copy.spreadsheet_revision_ids
        self.assertEqual(revisions[0].author_id, test_user_1)
        self.assertEqual(revisions[1].author_id, test_user_2)
        self.assertEqual(revisions[2].author_id, test_user_3)
        spreadsheet.with_user(self.env.ref("base.user_admin")).dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        self.assertEqual(spreadsheet.sudo().spreadsheet_revision_ids[-1].author_id, self.env.ref("base.user_admin"))

    def test_keep_original_spreadsheet_revision_timestamps(self):
        with freeze_time("2025-01-01 12:00:00"):
            spreadsheet = self.env["spreadsheet.test"].create({})
            spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            spreadsheet.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        with freeze_time("2025-01-01 23:00:00"):
            copy = spreadsheet.copy()
            revisions = copy.spreadsheet_revision_ids
            self.assertEqual(revisions[0].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            self.assertEqual(revisions[1].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            self.assertEqual(revisions[2].revision_date, datetime(2025, 1, 1, 12, 0, 0))
            copy.dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
            self.assertEqual(
                copy.spreadsheet_revision_ids[-1].revision_date,
                datetime(2025, 1, 1, 23, 0, 0),
            )

    def test_get_search_arch(self):

        # default search view
        arch = '<search><field name="name"/></search>'
        self.env["ir.ui.view"].create({
            "name": "Search View",
            "model": "res.partner",
            "type": "search",
            "arch": arch,
        })
        action = self.env["ir.actions.act_window"].create({
            "name": "Action2",
            "res_model": "res.partner",
        })
        xml_id = "spreadsheet_test_partner_search_view"
        module = "test_spreadsheet_edition"
        self.env["ir.model.data"].create({
            "name": xml_id,
            "model": "ir.actions.act_window",
            "module": module,
            "res_id": action.id,
        })
        xml_id = f"{module}.{xml_id}"
        result = self.env["spreadsheet.mixin"].get_search_view_archs([xml_id])
        self.assertEqual(result, {"res.partner": [arch]})

        # with a custom search view
        custom_arch = '<search><field name="name" string="custom search view"/></search>'
        custom_search_view = self.env["ir.ui.view"].create({
            "name": "Custom Search View",
            "model": "res.partner",
            "type": "search",
            "arch": custom_arch,
        })
        action.search_view_id = custom_search_view
        result = self.env["spreadsheet.mixin"].get_search_view_archs([xml_id])
        self.assertEqual(result, {"res.partner": [custom_arch]})
