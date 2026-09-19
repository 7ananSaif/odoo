from psycopg2 import IntegrityError
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged('-at_install', 'post_install')
class TestProjectProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # test create a db with just a url
        # this is in the setUpClass as we will reuse it in each test
        cls.database = cls.env['project.project'].create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'https://anotherdb.that.doesnt.exist',
        }])

    def test_create_projects_without_a_url(self):
        # This shouldn't raise any error
        self.env['project.project'].create([{'name': 'Regular Project'}])

        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env['project.project'].create([{'name': 'Regular Project', 'database_hosting': 'other'}])

    def test_write_projects_without_a_url(self):
        regular_project = self.env['project.project'].create([{'name': 'Regular Project'}])
        saas_database = self.env['project.project'].create([{'name': 'Online db', 'database_hosting': 'saas', 'database_url': 'https://saas.tld'}])
        paas_database = self.env['project.project'].create([{'name': 'Odoo.sh db', 'database_hosting': 'paas', 'database_url': 'https://paas.tld'}])
        premise_database = self.env['project.project'].create([{'name': 'On Premise db', 'database_hosting': 'premise', 'database_url': 'https://premise.tld'}])
        other_database = self.env['project.project'].create([{'name': 'Other db', 'database_hosting': 'other', 'database_url': 'https://other.tld'}])

        for db in saas_database + paas_database + premise_database + other_database:
            with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
                db.database_url = False

        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            regular_project.database_hosting = 'other'

        # This shouldn't raise any error, even if not all database have a URL and not all projects are databases
        (regular_project + saas_database + paas_database + premise_database + other_database).write_uid = self.ref('base.user_admin')
        # database_url can be set without error even if there is no database_hosting
        regular_project.database_url = 'https://regular.tld'
        # once database_url is set, database_hosting can be set without error
        regular_project.database_hosting = 'other'

    def test_action_database_connect_other(self):
        self.database.database_hosting = 'other'

        action = self.database.action_database_connect()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': self.database.database_url,
            'target': 'new',
        })

    @patch('requests.sessions.Session.request')
    def test_action_database_connect_saas(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = 'the_database_uuid'

        action = self.database.action_database_connect()
        mock_request.assert_called_once()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': 'https://www.odoo.com/my/databases/connect/the_database_uuid',
            'target': 'new',
        })

    @patch('requests.sessions.Session.request')
    def test_action_database_connect_saas_with_error(self, mock_request):
        mock_request.return_value.status_code = 500
        mock_request.return_value.json.return_value = {'message': 'Some error'}

        action = self.database.action_database_connect()
        mock_request.assert_called_once()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': f'{self.database.database_url}/web',
            'target': 'new',
        })

    def test_action_database_connect_premise_172(self):
        self.database.database_hosting = 'premise'
        self.database.database_version = 'saas~17.2'

        action = self.database.action_database_connect()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': 'https://anotherdb.that.doesnt.exist/odoo',
            'target': 'new',
        })

    def test_action_database_connect_premise_171(self):
        self.database.database_hosting = 'premise'
        self.database.database_version = 'saas~17.1'

        action = self.database.action_database_connect()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': 'https://anotherdb.that.doesnt.exist/web',
            'target': 'new',
        })
