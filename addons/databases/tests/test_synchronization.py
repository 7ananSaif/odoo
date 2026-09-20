from unittest.mock import call, MagicMock, patch
import xmlrpc.client

from .common import TestDatabasesCommon

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import freeze_time, tagged
from odoo.tests.common import users


@tagged('-at_install', 'post_install')
class TestSynchronization(TestDatabasesCommon):

    def mock_json2_calls_for_db(self, fqdn, version='dont-write-it-to-project', users=[], kpis=[]):
        self.json2_mocked_calls[fqdn]['version'] = version
        self.json2_mocked_calls[fqdn]['res.users']['search_read'] = users
        self.json2_mocked_calls[fqdn]['kpi.provider']['get_kpi_summary'] = kpis

    @users('db_manager@company.tld')
    def test_synchronization_disabled(self):
        # Clearing one of the two keys is enough to disable the synchronization to Odoo.com
        self.env['ir.config_parameter'].sudo().set_param('databases.odoocom_apiuser', False)

        self.env['project.project'].action_synchronize_all_databases()

        self.mock_requests_request.authenticate.assert_not_called()
        self.mock_requests_request.execute_kw.assert_not_called()

    @users('db_manager@company.tld')
    def test_synchronize_databases(self):
        """Synchronize the databases from the Odoo.com SaaS"""
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.assertCountEqual(self.mock_requests_request.mock_calls[:1], [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
        ])
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'Odoo', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'other_user@odoo.com', 'version': '17.0+e'},
        ]
        action = Project.action_synchronize_all_databases()
        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'Odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
        ])

        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "0 new databases, 1 updated.")

    @users('db_manager@company.tld')
    def test_db_synchronize_several_dbs(self):
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
            {'name': 'titi-sarl', 'url': 'http://titi-sarl.my.odoo.test', 'login': 'admin@titi-sarl.fr', 'version': '17.0+e'},
            {'name': 'toto-nv', 'url': 'http://toto-nv.my.odoo.test', 'login': 'contact@toto-nv.be', 'version': '18.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        self.mock_json2_calls_for_db('titi-sarl.my.odoo.test')
        self.mock_json2_calls_for_db('toto-nv.my.odoo.test')
        action = Project.action_synchronize_all_databases()

        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "3 new databases, 3 updated.")

        self.assertCountEqual(self.mock_requests_request.mock_calls[:1], [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
        ])
        new_projects = Project.search([], order='database_version')
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        # Other dbs should stay untouched
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'Odoo', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'other_user@odoo.com', 'version': '17.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        action = Project.action_synchronize_all_databases()
        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "0 new databases, 3 updated.")

        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'Odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

    def test_odoocom_db_synchronization(self):
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'cron-odoo-sa', 'url': 'http://cron-odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['version'] = '16.0+e'
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['res.users']['search_read'] = []
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['kpi.provider']['get_kpi_summary'] = []

        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases_with_odoocom()
        new_projects = Project.search([])

        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
        ])
        self.assertRecordValues(new_projects, [
            {
                'name': 'cron-odoo-sa',
                'database_name': 'cron-odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://cron-odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
                'database_last_synchro': False,
            },
        ])

        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database should now have been scanned",
        )

        with freeze_time('2025-01-01 23:59'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database shouldn't have been scanned yet",
        )

        with freeze_time('2025-01-02 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-02 00:00"),
            "The database should have been scanned",
        )

    @users('db_manager@company.tld')
    def test_synchronizing_a_saas_db_with_just_a_url_should_raise_an_error(self):
        """ Trying to synchronize one single database missing a db name should raise a User Friendly error"""
        db = self.env['project.project'].create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
        }])
        with self.assertRaisesRegex(
            UserError,
            "Error while connecting to http://anotherdb.that.doesnt.exist: "
            "We are missing the database name, the api login or the api key",
        ):
            db.action_database_synchronize()

    @users('db_manager@company.tld')
    def test_synchronizing_several_db_with_one_missing_its_name_and_api_info(self):
        """ In case several db gets synchronized, it shouldn't raise an Error but show it later on in the wizard

            - Create a fully legit db record by synchronizing all dbs with Odoo.com
            - Create manually a db missing its name and credentials
            - Try to synchronize both db at the same time
            => No error raised
            => Any issue should be reported in the wizard
        """
        # gets one legit database created through odoo.com synchronization and sync it
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        Project.create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
        }])
        dbs = Project.search([])
        self.assertEqual(len(dbs), 2)
        # Synchronizing several db shouldn't raise any error
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['version'] = '16.0+e'
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['search_read'] = []
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['kpi.provider']['get_kpi_summary'] = []
        action = dbs.action_database_synchronize()
        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(
            wizard.error_message.strip(),
            "Error while connecting to http://anotherdb.that.doesnt.exist: "
            "We are missing the database name, the api login or the api key",
        )

    @users('db_manager@company.tld')
    def test_synchronizing_all_databases_shouldnt_raise_but_should_report_any_issue(self):
        """ In case several db gets synchronized, it shouldn't raise an Error but show it later on in the wizard

            - Create manually a db missing its name and credentials
            - Synchronize everything, creating a new db record from sync
            => The db synced from odoo.com should be there
            => Any issue should be reported in the wizard
        """
        Project = self.env['project.project']
        Project.create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
        }])
        dbs = Project.search([])
        self.assertEqual(len(dbs), 1)

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['version'] = 'saas~18.3a1+e'

        # This shouldn't raise any error
        action = Project.action_synchronize_all_databases()
        dbs = Project.search([])
        self.assertRecordValues(dbs, [{
            'database_url': 'http://anotherdb.that.doesnt.exist',
            'database_version': False,
        }, {
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_version': 'saas~18.3',
        }])

        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(
            wizard.error_message.strip(),
            "Error while connecting to http://anotherdb.that.doesnt.exist: "
            "We are missing the database name, the api login or the api key",
        )

    @users('db_manager@company.tld')
    def test_synchronizing_all_databases_shouldnt_raise_if_project_template_not_configured(self):
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.env['ir.config_parameter'].sudo().set_param('databases.odoocom_project_template', False)

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        # This shouldn't raise any error
        self.env['project.project'].action_synchronize_all_databases()

    @users('db_manager@company.tld')
    def test_sync_pull_db_record_already_registered_as_saas_manually(self):
        """ If a db was manually created as a saas db and synchronized later on, the information should be udpated
            - Manually Create a saas db record with missing informations
            - Trigger the synchronization
            => The db informations should be updated
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': False,
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': False,
                'database_version': False,
            },
        ])

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

    @users('db_manager@company.tld')
    def test_db_on_premise_configured_shouldnt_be_modified(self):
        """ Fully configured on premise Db reported by odoo.com shouldn't be updated as it could wrongly override
            the data and be very frustrating to the db manager.
            - Manually create an on premise db
            - configure the login and apikey
            - update all dbs
            => The database should have been left untouched
            => The wizard should display a warning
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'premise',
            'database_name': 'odoo-sa',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_api_login': 'randomlogin@randomdomain.random',
            'database_api_key': 'random api key, amazing',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'randomlogin@randomdomain.random',
                'database_api_key': 'random api key, amazing',
            },
        ])

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'somethingelse@wout.wout', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        action = Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'randomlogin@randomdomain.random',
                'database_api_key': 'random api key, amazing',
                'database_version': False,
            },
        ])
        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(
            wizard.error_message.strip(),
            "The database http://odoo-sa.my.odoo.test is registered as a saas database in odoo.com. "
            "As it seems to be configured we have left it as is.",
        )

    @users('db_manager@company.tld')
    def test_db_on_premise_not_configured_should_be_updated_to_saas_db(self):
        """ A NOT configured on premise Db reported by odoo.com should be updated with odoo.com data
            - Manually create an on premise db
            - update all dbs
            => The database should have been updated and be reported as a saas databases
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'premise',
            'database_url': 'http://odoo-sa.my.odoo.test',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': False,
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': False,
                'database_version': False,
            },
        ])

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_without_configuration(self):
        self.env['ir.config_parameter'].sudo().set_param('databases.odoocom_apiuser', False)

        wizard = self.env['databases.synchronization.wizard'].create({})

        # This shouldn't raise any error
        wizard._do_update_from_odoocom()

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_authenticate_error(self):
        # Simulate an invalid API key error
        self.mock_requests_request.configure_mock(**{
            'side_effect': None,
            'return_value.status_code': 401,
            'return_value.json.return_value': {'message': 'Invalid apikey'},
        })

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: Invalid apikey\n')

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_call_error(self):
        # Simulate an exception
        self.mock_requests_request.configure_mock(**{
            'side_effect': None,
            'return_value.status_code': 422,
            'return_value.json.return_value': {'message': 'Some error'},
        })

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: Some error\n')

    @users('db_manager@company.tld')
    def test_user_management(self):
        database = self.env['project.project'].create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_name': 'odoo-sa',
            'database_api_login': 'admin',
            'database_api_key': 'admin_apikey',
        }])
        invite_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'invite',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })

        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['web_create_users'] = True
        invite_wizard.action_invite_users()
        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/web_create_users', data=None, json={
                'emails': ['employee@company.tld'],
                'context': {'no_reset_password': True},
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
        ])
        self.assertFalse(invite_wizard.error_message)

        self.mock_requests_request.reset_mock()
        remove_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'remove',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['search'] = [23]
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['write'] = True
        invite_wizard.action_remove_users()
        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/search', data=None, json={
                'domain': [('login', 'in', ['employee@company.tld'])],
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/write', data=None, json={
                'ids': [23],
                'values': {'active': False},
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
        ])

        self.assertFalse(remove_wizard.error_message)


@tagged('-at_install', 'post_install')
class TestXmlRpcSynchronization(TestDatabasesCommon):

    def setUp(self):
        super().setUp()

        # Simulate a server where /json/2 is not implemented
        self.mock_requests_request.configure_mock(**{
            'side_effect': None,
            'return_value.status_code': 303,
        })
        del self.mock_requests_request

        def object_execute_kw(db, uid, pwd, model, method, *args, **kwargs):
            return self.object_execute_kw[model][method]

        self.object_execute_kw = {}

        # Return a specific mock object for each ServerProxy
        self.mock_odoocom_xmlrpc_common = MagicMock(**{'authenticate.return_value': -42})  # uid = -42
        self.mock_odoocom_xmlrpc_object = MagicMock(**{'execute_kw.side_effect': object_execute_kw})
        self.odoo_sa_xmrpc_common = MagicMock(**{'authenticate.return_value': -128})
        self.odoo_sa_xmrpc_object = MagicMock()
        self.call_resolution_per_uri = {
            "https://www.odoo.com/xmlrpc/2/common": self.mock_odoocom_xmlrpc_common,
            "https://www.odoo.com/xmlrpc/2/object": self.mock_odoocom_xmlrpc_object,
            "http://odoo-sa.my.odoo.test/xmlrpc/2/common": self.odoo_sa_xmrpc_common,
            "http://odoo-sa.my.odoo.test/xmlrpc/2/object": self.odoo_sa_xmrpc_object,
        }
        self.startPatcher(patch("xmlrpc.client.ServerProxy", side_effect=lambda uri: self.call_resolution_per_uri[uri]))

    def set_returned_databases_list(self, databases_list):
        for database in databases_list:
            self.call_resolution_per_uri.setdefault(f"{database['url']}/xmlrpc/2/common", MagicMock())\
                    .version.configure_mock(return_value={'server_serie': database['version']})
            self.call_resolution_per_uri.setdefault(f"{database['url']}/xmlrpc/2/object", MagicMock())
        self.object_execute_kw.setdefault('odoo.database', {})['list'] = databases_list

    @users('db_manager@company.tld')
    def test_synchronize_databases(self):
        """Synchronize the databases from the Odoo.com SaaS"""
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.mock_odoocom_xmlrpc_common.authenticate.assert_called_with('openerp', 'someuser@odoo.com', 'privateKey', {})
        self.mock_odoocom_xmlrpc_object.execute_kw.assert_called_with('openerp', -42, 'privateKey', 'odoo.database', 'list', [])
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

        # Already-seen database updates the project, based on the URL
        self.set_returned_databases_list([
            {'name': 'odoo-bis', 'login': 'other_user@odoo.com', 'version': '17.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        action = Project.action_synchronize_all_databases()
        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-bis',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
        ])

        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "0 new databases, 1 updated.")

    @users('db_manager@company.tld')
    def test_db_synchronize_several_dbs(self):
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
            {'name': 'titi-sarl', 'login': 'admin@titi-sarl.fr', 'version': '17.0+e', 'url': 'http://titi-sarl.my.odoo.test'},
            {'name': 'toto-nv', 'login': 'contact@toto-nv.be', 'version': '18.0+e', 'url': 'http://toto-nv.my.odoo.test'},
        ])
        action = Project.action_synchronize_all_databases()

        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "3 new databases, 3 updated.")

        self.mock_odoocom_xmlrpc_common.authenticate.assert_called_with('openerp', 'someuser@odoo.com', 'privateKey', {})
        self.mock_odoocom_xmlrpc_object.execute_kw.assert_called_with('openerp', -42, 'privateKey', 'odoo.database', 'list', [])
        new_projects = Project.search([], order='database_version')
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        # Other dbs should stay untouched
        self.set_returned_databases_list([
            {'name': 'odoo', 'login': 'other_user@odoo.com', 'version': '17.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        action = Project.action_synchronize_all_databases()
        wizard = self.env['databases.synchronization.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.summary_message, "0 new databases, 3 updated.")

        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

    def test_odoocom_db_synchronization(self):
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'cron-odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://cron-odoo-sa.my.odoo.test'},
        ])
        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases_with_odoocom()
        new_projects = Project.search([])

        self.mock_odoocom_xmlrpc_common.authenticate.assert_called_with('openerp', 'someuser@odoo.com', 'privateKey', {})
        self.mock_odoocom_xmlrpc_object.execute_kw.assert_called_with('openerp', -42, 'privateKey', 'odoo.database', 'list', [])
        self.assertRecordValues(new_projects, [
            {
                'name': 'cron-odoo-sa',
                'database_name': 'cron-odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://cron-odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
                'database_last_synchro': False,
            },
        ])

        cron_odoo_sa_xmlrpc_common = MagicMock()
        cron_odoo_sa_xmlrpc_common.version.return_value = {'server_serie': 'saas~18.4'}
        self.call_resolution_per_uri['http://cron-odoo-sa.my.odoo.test/xmlrpc/2/common'] = cron_odoo_sa_xmlrpc_common
        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database should now have been scanned",
        )

        with freeze_time('2025-01-01 23:59'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database shouldn't have been scanned yet",
        )

        with freeze_time('2025-01-02 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-02 00:00"),
            "The database should have been scanned",
        )

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_authenticate_error(self):
        self.mock_odoocom_xmlrpc_common.authenticate = MagicMock(side_effect=xmlrpc.client.Fault(42, 'TestFaultString'))

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: TestFaultString\n')

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_call_error(self):
        self.mock_odoocom_xmlrpc_object.execute_kw = MagicMock(side_effect=xmlrpc.client.Fault(42, 'TestFaultString'))

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: TestFaultString\n')

    @users('db_manager@company.tld')
    def test_user_management(self):
        database = self.env['project.project'].create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_name': 'odoo-sa',
            'database_api_login': 'admin',
            'database_api_key': 'admin_apikey',
        }])
        invite_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'invite',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })

        invite_wizard.action_invite_users()
        self.assertCountEqual(self.odoo_sa_xmrpc_common.authenticate.mock_calls, [
            call('odoo-sa', 'admin', 'admin_apikey', {}),
        ])
        self.assertCountEqual(self.odoo_sa_xmrpc_object.execute_kw.mock_calls, [
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'web_create_users', [], {
                'emails': ['employee@company.tld'],
                'context': {'no_reset_password': True},
            }),
        ])
        self.assertFalse(invite_wizard.error_message)

        self.odoo_sa_xmrpc_common.authenticate.reset_mock()
        self.odoo_sa_xmrpc_object.execute_kw.reset_mock()
        self.odoo_sa_xmrpc_object.execute_kw.side_effect = [[1024], True]
        remove_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'remove',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })
        invite_wizard.action_remove_users()
        # TODO: self.odoo_sa_xmrpc_common.authenticate.assert_not_called()  # should have recycled the client
        self.assertCountEqual(self.odoo_sa_xmrpc_object.execute_kw.mock_calls, [
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'search', [
                [('login', 'in', ['employee@company.tld'])],
            ]),
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'write', [
                [1024],
                {'active': False},
            ]),
        ])

        self.assertFalse(remove_wizard.error_message)
