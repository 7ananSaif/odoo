from .common import TestDatabasesCommon

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import users


@tagged('-at_install', 'post_install')
class TestDatabasesSecurity(TestDatabasesCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        common_fields = {
            'database_hosting': 'saas',
            'database_api_login': 'login',
            'database_name': 'db_name',
        }
        cls.env['project.project'].create([{
            **common_fields,
            'name': 'Client 1',
            'database_url': 'http://1.doesnt.exist',
            'database_user_ids': [Command.create({'login': 'employee@company.tld', 'name': 'User'})],
        }, {
            **common_fields,
            'name': 'Client 2',
            'database_url': 'http://2.doesnt.exist',
            'database_user_ids': [Command.create({'login': 'project_user@company.tld', 'name': 'User'})],
        }, {
            **common_fields,
            'name': 'Client 3',
            'database_url': 'http://3.doesnt.exist',
            'database_user_ids': [Command.create({'login': 'project_manager@company.tld', 'name': 'User'})],
        }, {
            **common_fields,
            'name': 'Client 4',
            'database_url': 'http://4.doesnt.exist',
            'database_user_ids': [Command.create({'login': 'db_user@company.tld', 'name': 'User'})],
        }, {
            **common_fields,
            'name': 'Client 5',
            'database_url': 'http://5.doesnt.exist',
            'database_user_ids': [Command.create({'login': 'db_manager@company.tld', 'name': 'User'})],
        }])

        action = cls.env['project.template.create.wizard'].with_context(databases_template=True).create([{
            **common_fields,
            'template_id': cls.env.ref('databases.database_default_template').id,
            'name': 'Client 6',
            'database_url': 'http://6.doesnt.exist',
        }]).create_project_from_template()
        cls.env['project.project'].browse(action['context']['active_id']).write({
            'database_user_ids': [
                Command.create({'login': 'employee@company.tld', 'name': 'User'}),
                Command.create({'login': 'project_user@company.tld', 'name': 'User'}),
                Command.create({'login': 'project_manager@company.tld', 'name': 'User'}),
                Command.create({'login': 'db_user@company.tld', 'name': 'User'}),
                Command.create({'login': 'db_manager@company.tld', 'name': 'User'}),
            ],
        })

    @users('employee@company.tld', 'project_user@company.tld', 'project_manager@company.tld')
    def test_employee_without_db_access_shouldnt_have_access_to_any_database(self):
        self.assertFalse(
            self.env['project.project'].search([('database_hosting', '!=', False)]),
            "An employee without any databases access shouldn't see any database",
        )

    @users('db_manager@company.tld')
    def test_db_manager_should_access_to_all_db(self):
        self.assertEqual(
            self.env['project.project'].search([('database_hosting', '!=', False)]).mapped('name'),
            ['Client 1', 'Client 2', 'Client 3', 'Client 4', 'Client 5', 'Client 6'],
            "The database manager should be able to see all databases"
        )

    @users('db_user@company.tld')
    def test_db_user_should_have_access_to_db_it_has_been_assigned_to(self):
        self.assertEqual(
            self.env['project.project'].search([('database_hosting', '!=', False)]).mapped('name'),
            ['Client 4', 'Client 6'],
        )

    @users('employee@company.tld')
    def test_employee_given_group_should_have_access(self):
        # unless they have a database user role
        self.user_employee.group_ids = [Command.link(self.ref('databases.group_databases_user'))]
        self.assertEqual(
            self.env['project.project'].search([('database_hosting', '!=', False)]).mapped('name'),
            ['Client 1', 'Client 6'],
            "If the employee was given access, it can see the db he has a user in",
        )

    @users('employee@company.tld')
    def test_synchronization_unauthorized(self):
        with self.assertRaises(AccessError):
            self.env['project.project'].action_synchronize_all_databases()

        # Ensure that above of the Odoo AccessError, there isn't any call made to the outsite world
        self.mock_requests_request.authenticate.assert_not_called()
