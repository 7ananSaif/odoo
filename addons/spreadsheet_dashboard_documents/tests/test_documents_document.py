from odoo.tests.common import HttpCase, new_test_user


class TestDocumentsDocument(HttpCase):
    def test_can_add_to_dashboard_admin(self):
        admin = new_test_user(
            self.env, "Test user",
            groups="spreadsheet_dashboard.group_dashboard_manager,documents.group_documents_user"
        )
        self.authenticate(admin.login, admin.password)
        document = self.env["documents.document"].with_user(admin).create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertTrue(response.json()['can_add_to_dashboard'])

    def test_can_add_to_dashboard_non_admin(self):
        user = new_test_user(
            self.env, "Test user", groups="base.group_user,documents.group_documents_user"
        )
        self.authenticate(user.login, user.password)
        document = self.env["documents.document"].with_user(user).create(
            {
                "name": "a document",
                "spreadsheet_data": r'{"sheets": []}',
                "handler": "spreadsheet",
                "mimetype": "application/o-spreadsheet",
            }
        )
        response = self.url_open('/spreadsheet/data/documents.document/%s' % document.id)
        self.assertFalse(response.json()['can_add_to_dashboard'])
