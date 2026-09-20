import json

from odoo import http

from odoo.tests.common import HttpCase, new_test_user
from odoo.tools.misc import mute_logger

from .common import SpreadsheetTestCommon


class TestSpreadsheetDocumentController(SpreadsheetTestCommon, HttpCase):

    def test_upload_osheet_json_file(self):
        self.authenticate('admin', 'admin')
        folder = self.env['documents.document'].create({'name': 'Test folder', 'type': 'folder', 'access_internal': 'edit'})

        data = {'sheets': []}

        for name in ['test.osheet.json', 'test.osheet (5).json', 'test.osheet(5).json']:
            with self.subTest(name=name):
                response = self.url_open(
                    url='/documents/upload',
                    data={
                        'access_token': folder.access_token,
                        'csrf_token': http.Request.csrf_token(self),
                    },
                    files=[('ufile', (name, json.dumps(data), 'application/json'))],
                )

                self.assertEqual(response.status_code, 200)
                document = self.env['documents.document'].browse(response.json())
                self.assertEqual(document.handler, 'spreadsheet')
                self.assertEqual(document.spreadsheet_data, json.dumps(data))

    def test_upload_osheet_not_json_file(self):
        self.authenticate('admin', 'admin')
        folder = self.env['documents.document'].create({'name': 'Test folder', 'type': 'folder', 'access_internal': 'edit'})
        data = 'not a json file'
        response = self.url_open(
            url='/documents/upload',
            data={
                'access_token': folder.access_token,
                'csrf_token': http.Request.csrf_token(self),
            },
            files=[('ufile', ('test.osheet.json', data, 'text/plain'))],
        )

        self.assertEqual(response.status_code, 200)
        document = self.env['documents.document'].browse(response.json())
        self.assertFalse(document.handler)
        self.assertFalse(document.spreadsheet_data)
        self.assertEqual(document.folder_id, folder)

    @mute_logger('odoo.http')
    def test_upload_invalid_osheet_json_file(self):
        self.authenticate('admin', 'admin')
        folder = self.env['documents.document'].create({'name': 'Test folder', 'type': 'folder', 'access_internal': 'edit'})
        data = {
            'sheets': [],
            'lists': {
                '1': {
                    'model': 'my.invalid.model',
                    'columns': [],
                    'domain': [],
                    'context': {},
                    'orderBy': [],
                    'id': '1',
                    'name': 'Purchase Orders by Untaxed Amount'
                }
            }
        }
        response = self.url_open(
            url='/documents/upload',
            data={
                'access_token': folder.access_token,
                'csrf_token': http.Request.csrf_token(self),
            },
            files=[('ufile', ('test.osheet.json', json.dumps(data), 'application/json'))],
        )

        self.assertIn('Looks like the spreadsheet file contains invalid data.', response.text)
        self.assertEqual(response.status_code, 422)

    def test_get_blank_spreadsheet_data(self):
        self.authenticate(self.spreadsheet_user.login, self.spreadsheet_user.password)
        spreadsheet = self.create_spreadsheet()
        response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet.id)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['data'], {})
        self.assertEqual(result['revisions'], [], 'It should not have past revisions')

    def test_get_active_spreadsheet_data(self):
        self.authenticate(self.spreadsheet_user.login, self.spreadsheet_user.password)
        spreadsheet = self.create_spreadsheet()
        commands = self.new_revision_data(spreadsheet)
        spreadsheet.dispatch_spreadsheet_message(commands)
        response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet.id)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        del commands['clientId']
        self.assertEqual(result['data'], {})
        self.assertEqual(result['revisions'], [commands], 'It should have past revisions')

    def test_read_internal_user_access(self):
        raoul = new_test_user(self.env, login='raoul')
        self.authenticate(raoul.login, raoul.password)
        document = self.env['documents.document'].create(
            {
                'spreadsheet_data': b'{}',
                'folder_id': self.folder.id,
                'handler': 'spreadsheet',
                'mimetype': 'application/o-spreadsheet',
                'access_internal': 'edit',
            }
        )
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['isReadonly'], False)
        self.assertEqual(response.json()['data'], {})

    @mute_logger('odoo.http')
    def test_get_data_with_token(self):
        document = self.create_spreadsheet()

        document.access_via_link = 'view'
        document.access_internal = 'none'
        document.folder_id.access_via_link = 'none'
        document.folder_id.access_internal = 'none'
        access_token = document.sudo().access_token

        raoul = new_test_user(self.env, login='raoul')
        alice = new_test_user(self.env, login='alice')

        self.env['documents.access'].create({
            'document_id': document.id,
            'partner_id': raoul.partner_id.id,
            'role': 'edit',
        })

        self.authenticate(alice.login, alice.password)  # readonly access with token
        # without token
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertEqual(response.status_code, 403, 'Forbidden')

        # with wrong token
        response = self.url_open('/spreadsheet/data/documents.document/%s/a-wrong-token' % document.id)
        self.assertEqual(response.status_code, 403, 'Forbidden')

        # with token
        response = self.url_open('/spreadsheet/data/documents.document/%s/%s' % (document.id, access_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['isReadonly'], True)

        # without token and access
        self.authenticate('raoul', 'raoul')  # explicit edit access
        response = self.url_open('/spreadsheet/data/documents.document/%s' % (document.id,))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['isReadonly'], False)

        # with token and access
        response = self.url_open('/spreadsheet/data/documents.document/%s/%s' % (document.id, access_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['isReadonly'], False)

    @mute_logger('odoo.http')
    def test_get_readonly_data_with_token(self):
        'Readonly access'
        document = self.create_spreadsheet()

        document.access_via_link = 'view'
        document.access_internal = 'none'
        document.folder_id.access_via_link = 'none'
        document.folder_id.access_internal = 'none'

        access_token = document.sudo().access_token

        raoul = new_test_user(self.env, login='raoul')
        self.authenticate(raoul.login, raoul.password)
        # without token
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertEqual(response.status_code, 403, 'Forbidden')

        # with token
        response = self.url_open('/spreadsheet/data/documents.document/%s/%s' % (document.id, access_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['isReadonly'], True)

    def test_spreadsheet_with_token_from_folder_share(self):
        document_1 = self.create_spreadsheet()
        self.create_spreadsheet()
        folder = document_1.folder_id
        self.assertEqual(len(folder.children_ids), 2, 'there are more than one document in the folder')
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document_1.id)
        self.assertEqual(response.status_code, 200)

    def test_read_portal_user_with_doc_access(self):
        document = self.create_spreadsheet()
        portal_user = new_test_user(self.env, login="Raoul", groups="base.group_portal")
        self.authenticate(portal_user.login, portal_user.password)
        self.env['documents.access'].create({
            'document_id': document.id,
            'partner_id': portal_user.partner_id.id,
            'role': 'view',
        })
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertEqual(response.status_code, 200)

    def test_join_snapshot_request(self):
        raoul = new_test_user(self.env, login='raoul')
        self.authenticate(raoul.login, raoul.password)
        spreadsheet = self.create_spreadsheet()
        with self._freeze_time('2020-02-02 18:00'):
            spreadsheet.dispatch_spreadsheet_message(
                self.new_revision_data(spreadsheet)
            )
        spreadsheet.access_internal = 'view'
        with self._freeze_time('2020-02-03 18:00'):
            response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet.id)
            # readonly
            self.assertFalse(
                response.json().get('snapshot_requested'),
                'It should not have requested a snapshot',
            )
            # edit
            spreadsheet.access_internal = 'edit'
            self.folder.access_internal = 'edit'
            self.assertTrue(spreadsheet._should_be_snapshotted())
            response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet.id)
            self.assertTrue(
                response.json().get('snapshot_requested'),
                'It should have requested a snapshot',
            )

    def test_spreadsheet_name_is_a_string(self):
        self.authenticate(self.spreadsheet_user.login, self.spreadsheet_user.password)
        spreadsheet = self.create_spreadsheet(name='')
        self.assertEqual(spreadsheet.name, '')
        self.assertFalse(spreadsheet.display_name)
        response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet.id)
        self.assertEqual(response.json()['name'], '')
