from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.addons.documents.tests.test_documents_sharing import TestDocumentsSharing
from odoo.tests import Form, users


class TestSpreadsheetDocumentsSharing(TransactionCaseDocuments):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["documents.document"].create({
            "name": "Test folder",
            "type": "folder",
            "access_internal": "view",
            "access_via_link": "view",
        })
        cls.frozen_spreadsheets = cls.env['documents.document'].create([
            {'name': f'Frozen spreadsheet_{i}', 'handler': 'frozen_spreadsheet',
             'folder_id': cls.folder.id, 'owner_id': cls.document_manager.id}
            for i in range(2)
        ])
        cls.spreadsheet = cls.env['documents.document'].create([
            {'name': f'Spreadsheet_{i}', 'handler': 'spreadsheet',
             'folder_id': cls.folder.id, 'owner_id': cls.document_manager.id}
            for i in range(2)
        ])
        cls.non_spreadsheet = cls.env['documents.document'].create([
            {'name': f'Non_spreadsheet_{i}', 'folder_id': cls.folder.id, 'owner_id': cls.document_manager.id}
            for i in range(2)
        ])
        cls.docs = cls.frozen_spreadsheets | cls.spreadsheet | cls.non_spreadsheet
        (cls.frozen_spreadsheets | cls.spreadsheet | cls.non_spreadsheet).action_update_access_rights(
            partners={cls.doc_user.partner_id: ('view', False), cls.portal_user.partner_id: ('view', False)})
        cls.partners = cls.frozen_spreadsheets[0].access_ids.partner_id

    def create_documents_sharing(self, documents):
        return self.env['documents.sharing'].browse(
            [self.env['documents.sharing'].action_open(documents.ids)['res_id']])

    @staticmethod
    def get_display_names(records):
        return ', '.join(records.sorted('display_name').mapped('display_name'))

    @users("dtdm")
    def test_invite_frozen_edit_error(self):
        with Form(self.create_documents_sharing(self.docs)) as form:
            self.assertFalse(form.error_message_spreadsheet)
            form.invite_partner_ids = self.doc_user.partner_id
            form.invite_role = 'edit'
            self.assertIn("Read only spreadsheet(s):", form.error_message_spreadsheet)
            self.assertIn(self.get_display_names(self.frozen_spreadsheets), form.error_message_spreadsheet)

    @users("dtdm")
    def test_invite_to_non_internal_user_edit_error(self):
        with Form(self.create_documents_sharing(self.spreadsheet | self.non_spreadsheet)) as form:
            self.assertFalse(form.error_message_spreadsheet)
            form.invite_partner_ids = (self.doc_user | self.portal_user).partner_id
            form.invite_role = 'edit'
            self.assertIn("You can not share spreadsheet(s) in edit mode", form.error_message_spreadsheet)
            self.assertIn("to non-internal users.", form.error_message_spreadsheet)
            self.assertIn(self.get_display_names(self.spreadsheet), form.error_message_spreadsheet)
            self.assertIn(self.portal_user.partner_id.name, form.error_message_spreadsheet)

    @users("dtdm")
    def test_share_frozen_edit_error(self):
        for operation, expected_partners in (
            ('set_doc_user_edit', self.doc_user.partner_id),
            ('set_access_internal_edit', self.env['res.partner']),
            ('set_access_via_link_edit', self.env['res.partner']),
        ):
            with self.subTest(operation=operation), Form(self.create_documents_sharing(self.docs)) as form:
                self.assertFalse(form.error_message_spreadsheet)
                if operation == 'set_doc_user_edit':
                    with TestDocumentsSharing.form_get_access_edit(form, self.doc_user.partner_id) as access_edit_form:
                        access_edit_form.role = 'edit'
                elif operation == 'set_access_internal_edit':
                    form.access_internal = 'edit'
                elif operation == 'set_access_via_link_edit':
                    form.access_via_link = 'edit'
                self.assertIn('Read only spreadsheet(s):', form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(self.frozen_spreadsheets), form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(expected_partners), form.error_message_spreadsheet)
                self.assertFalse(form.has_warning_link_with_more_rights)

    @users("dtdm")
    def test_share_to_non_internal_user_edit_error(self):
        for operation, expected_errors, expected_partner_error in [
            ('set_portal_user_edit', ["You can not share spreadsheet(s) in edit mode", "to non-internal users"],
             self.portal_user.partner_id),
            ('set_access_via_link_edit', ["You cannot share spreadsheet(s) via link in edit mode"],
             self.env['res.partner']),
        ]:
            with (self.subTest(operation=operation),
                  Form(self.create_documents_sharing(self.spreadsheet | self.non_spreadsheet)) as form):
                self.assertFalse(form.error_message_spreadsheet)
                if operation == 'set_portal_user_edit':
                    with TestDocumentsSharing.form_get_access_edit(form, self.portal_user.partner_id) as access_form:
                        access_form.role = 'edit'
                elif operation == 'set_access_via_link_edit':
                    form.access_via_link = 'edit'
                for expected_error in expected_errors:
                    self.assertIn(expected_error, form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(self.spreadsheet), form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(expected_partner_error), form.error_message_spreadsheet)
