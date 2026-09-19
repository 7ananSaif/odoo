# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from psycopg2.errors import CheckViolation

from .common import SpreadsheetTestCommon
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

EXCEL_FILES = [
    {
        "content": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "path": "[Content_Types].xml",
    }
]


class SpreadsheetSharing(SpreadsheetTestCommon):

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_can_read_others(self):
        document = self.create_spreadsheet()
        alice = new_test_user(self.env, login="alice")
        bob = new_test_user(self.env, login="bob")
        self.env['documents.access'].create({
            'document_id': document.id,
            'partner_id': alice.partner_id.id,
            'role': 'edit',
        })
        self.env['documents.access'].create({  # Do not copy this access
            'document_id': document.id,
            'partner_id': bob.partner_id.id,
            'role': False,
            'last_access_date': date.today(),
        })
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            shared_spreadsheet_action = document.action_freeze_and_copy({}, b"")
        shared_spreadsheet = document.browse(shared_spreadsheet_action['id'])

        self.assertNotEqual(document.access_token, shared_spreadsheet.access_token)
        self.assertFalse(shared_spreadsheet.folder_id.owner_id)
        self.assertEqual(shared_spreadsheet.access_internal, 'view')
        self.assertTrue(shared_spreadsheet.with_user(self.spreadsheet_user).name, 'user can access the name.')

        # check that the access have been copied, and switched to "view" if needed
        access = shared_spreadsheet.access_ids
        self.assertEqual(len(access), 1)
        self.assertEqual(access.role, 'view')
        self.assertEqual(access.partner_id, alice.partner_id)

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_collaborative_dispatch_spreadsheet_with_token(self):
        document = self.create_spreadsheet()

        document.access_via_link = 'view'
        document.access_internal = 'none'
        document.folder_id.access_via_link = 'none'
        document.folder_id.access_internal = 'none'
        access_token = document.sudo().access_token

        raoul = new_test_user(self.env, login="raoul")
        alice = new_test_user(self.env, login="alice")

        self.env['documents.access'].create({
            'document_id': document.id,
            'partner_id': raoul.partner_id.id,
            'role': 'edit',
        })

        document = document.with_user(alice)

        revision = self.new_revision_data(document)

        # dispatch revision without access
        with self.assertRaises(AccessError):
            document.dispatch_spreadsheet_message(revision)

        # dispatch revision with wrong token
        with self.assertRaises(AccessError):
            document.dispatch_spreadsheet_message(revision, "a wrong token")

        # snapshot without token
        snapshot_revision = {
            "type": "SNAPSHOT",
            "serverRevisionId": document.sudo().current_revision_uuid,
            "nextRevisionId": "snapshot-revision-id",
            "data": {"revisionId": "snapshot-revision-id"},
        }
        with self.assertRaises(AccessError):
            document.dispatch_spreadsheet_message(snapshot_revision)

        # snapshot with wrong token
        snapshot_revision = {
            "type": "SNAPSHOT",
            "serverRevisionId": document.sudo().current_revision_uuid,
            "nextRevisionId": "snapshot-revision-id",
            "data": {"revisionId": "snapshot-revision-id"},
        }
        with self.assertRaises(AccessError):
            document.dispatch_spreadsheet_message(snapshot_revision, "a wrong token")

        # now, the user can access the spreadsheet
        document = document.with_user(raoul)
        self.assertEqual(document.user_permission, "edit")
        self.assertTrue(document._check_collaborative_spreadsheet_access(
            "write", access_token, raise_exception=False))

        revision = self.new_revision_data(document)

        # dispatch revision with access
        accepted = document.dispatch_spreadsheet_message(revision, access_token)
        self.assertEqual(accepted, True)

        # snapshot with access
        snapshot_revision = {
            "type": "SNAPSHOT",
            "serverRevisionId": document.sudo().current_revision_uuid,
            "nextRevisionId": "snapshot-revision-id",
            "data": {"revisionId": "snapshot-revision-id"},
        }
        accepted = document.dispatch_spreadsheet_message(snapshot_revision, access_token)
        self.assertEqual(accepted, True)

    @mute_logger('odoo.addons.base.models.ir_rule')
    def test_collaborative_readonly_dispatch_spreadsheet_with_token(self):
        """Readonly access"""
        document = self.create_spreadsheet()

        document.access_via_link = 'view'
        document.access_internal = 'none'
        document.folder_id.access_via_link = 'none'
        document.folder_id.access_internal = 'none'

        access_token = document.sudo().access_token

        user = new_test_user(self.env, login="raoul")
        document = document.with_user(user)
        with self.with_user("raoul"):

            revision = self.new_revision_data(document)
            # dispatch revision without token
            with self.assertRaises(AccessError):
                document.dispatch_spreadsheet_message(revision)

            # dispatch revision with wrong token
            with self.assertRaises(AccessError):
                document.dispatch_spreadsheet_message(revision, "a wrong token")

            # raise because of readonly access
            with self.assertRaises(AccessError):
                document.dispatch_spreadsheet_message(revision, access_token)

            # snapshot without token
            snapshot_revision = {
                "type": "SNAPSHOT",
                "serverRevisionId": document.sudo().current_revision_uuid,
                "nextRevisionId": "snapshot-revision-id",
                "data": b"{}",
            }
            with self.assertRaises(AccessError):
                document.dispatch_spreadsheet_message(snapshot_revision)

            # snapshot with token
            snapshot_revision = {
                "type": "SNAPSHOT",
                "serverRevisionId": document.sudo().current_revision_uuid,
                "nextRevisionId": "snapshot-revision-id",
                "data": b"{}",
            }
            with self.assertRaises(AccessError):
                document.dispatch_spreadsheet_message(snapshot_revision, access_token)

    @mute_logger('odoo.sql_db')
    def test_spreadsheet_can_not_share_write_access_to_portal(self):
        spreadsheet = self.create_spreadsheet()
        user_portal = new_test_user(self.env, login='alice', groups='base.group_portal')
        user_internal = new_test_user(self.env, login='eve')
        user_internal_archived = new_test_user(self.env, login='john')
        user_internal_archived.active = False
        partner = self.env['res.partner'].create({'name': 'Bob'})

        self.env['documents.access'].create({
            'document_id': spreadsheet.id,
            'partner_id': user_internal.partner_id.id,
            'role': 'edit',
        })

        self.env['documents.access'].create({
            'document_id': spreadsheet.id,
            'partner_id': user_internal_archived.partner_id.id,
            'role': 'edit',
        })

        with self.assertRaises(ValidationError):
            self.env['documents.access'].create({
                'document_id': spreadsheet.id,
                'partner_id': user_portal.partner_id.id,
                'role': 'edit',
            })

        with self.assertRaises(ValidationError):
            self.env['documents.access'].create({
                'document_id': spreadsheet.id,
                'partner_id': partner.id,
                'role': 'edit',
            })

        with self.assertRaises(CheckViolation):
            spreadsheet.access_via_link = 'edit'
            spreadsheet.flush_recordset()

        with self.assertRaises(CheckViolation):
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                frozen_action = spreadsheet.action_freeze_and_copy({}, b"")
            frozen = spreadsheet.browse(frozen_action['id'])
            frozen.access_via_link = 'edit'
            frozen.flush_recordset()

        with self.assertRaises(CheckViolation):
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                frozen_action = spreadsheet.action_freeze_and_copy({}, b"")
            frozen = spreadsheet.browse(frozen_action['id'])
            frozen.access_internal = 'edit'
            frozen.flush_recordset()
