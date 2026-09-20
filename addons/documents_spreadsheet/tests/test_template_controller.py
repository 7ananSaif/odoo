
from odoo.tests.common import HttpCase

from .common import SpreadsheetTestCommon


class TestSpreadsheetTemplateController(SpreadsheetTestCommon, HttpCase):

    def test_get_template_data(self):
        template = self.env['spreadsheet.template'].create({
            'spreadsheet_data': '{}',
            'name': 'Template name',
        })
        user = self.spreadsheet_user
        self.authenticate(user.login, user.password)
        response = self.url_open('/spreadsheet/data/spreadsheet.template/%s' % template.id)
        self.assertEqual(response.json()['data'], {})
        self.assertEqual(response.json()['revisions'], [], 'It should not have any initial revisions')

    def test_get_active_template_data(self):
        template = self.env['spreadsheet.template'].create({
            'spreadsheet_data': '{}',
            'name': 'Template name',
        })
        user = self.spreadsheet_user
        self.authenticate(user.login, user.password)
        commands = self.new_revision_data(template)
        template.dispatch_spreadsheet_message(commands)
        del commands['clientId']
        response = self.url_open('/spreadsheet/data/spreadsheet.template/%s' % template.id)
        self.assertEqual(response.json()['data'], {})
        self.assertEqual(response.json()['revisions'], [commands], 'It should have any initial revisions')

    def test_action_create_spreadsheet_with_user_locale(self):
        self.env.ref('base.lang_fr').active = True
        user = self.spreadsheet_user
        self.authenticate(user.login, user.password)
        user.lang = 'fr_FR'
        template = self.env['spreadsheet.template'].create({
            'name': 'Template name',
        })
        action = template.with_user(user).action_create_spreadsheet()
        spreadsheet_id = action['params']['spreadsheet_id']
        response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet_id)
        revision = response.json()['revisions']
        self.assertEqual(len(revision), 1)
        self.assertEqual(revision[0]['commands'][0]['type'], 'UPDATE_LOCALE')
        self.assertEqual(revision[0]['commands'][0]['locale']['code'], 'fr_FR')

    def test_action_create_spreadsheet_with_existing_revision_with_user_locale(self):
        self.env.ref('base.lang_fr').active = True
        user = self.spreadsheet_user
        self.authenticate(user.login, user.password)
        user.lang = 'fr_FR'
        template = self.env['spreadsheet.template'].create({
            'name': 'Template name',
        })
        template.dispatch_spreadsheet_message(self.new_revision_data(template))
        action = template.with_user(user).action_create_spreadsheet()
        spreadsheet_id = action['params']['spreadsheet_id']
        response = self.url_open('/spreadsheet/data/documents.document/%s' % spreadsheet_id)
        revision = response.json()['revisions']
        self.assertEqual(len(revision), 2)
        self.assertEqual(revision[-1]['commands'][0]['type'], 'UPDATE_LOCALE')
        self.assertEqual(revision[-1]['commands'][0]['locale']['code'], 'fr_FR')
