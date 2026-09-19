# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import UserError, AccessError
from odoo.tests.common import TransactionCase
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tools import mute_logger


class TestDocumentsDocumentFolder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_folder = cls.env['documents.document'].create({
            'name': 'Parent',
            'type': 'folder',
        })
        cls.folder = cls.env['documents.document'].create({
            'name': 'Folder',
            'type': 'folder',
            'folder_id': cls.parent_folder.id,
        })
        cls.child_folder = cls.env['documents.document'].create({
            'name': 'Child',
            'type': 'folder',
            'folder_id': cls.folder.id,
        })
        cls.document = cls.env['documents.document'].create({
            'raw': b'TEST',
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'folder_id': cls.child_folder.id
        })
        cls.folders = cls.parent_folder | cls.folder | cls.child_folder

        cls.user_portal = mail_new_test_user(
            cls.env,
            login='portal_test',
            groups='base.group_portal',
            company_id=cls.env.ref('base.main_company').id,
            name='portal',
            notification_type='email'
        )

    def test_folder_archive_unarchive(self):
        """ General archive/restore test """
        self.folder.action_archive()
        self.assertEqual(
            (self.folders | self.document).mapped('active'),
            [True, False, False, False],
        )
        self.assertEqual(self.folders.exists(), self.folders,
            "No folder/document should have been deleted")

        with self.assertRaises(UserError) as capture:
            self.child_folder.action_unarchive()
        self.assertEqual(
            capture.exception.args[0],
            "Item(s) you wish to restore are included in archived folders. "
            "To restore these items, you must restore the following including folders instead:"
            "\n"
            "- Folder"
        )

        self.folder.action_unarchive()
        self.assertEqual(
            (self.folders | self.document).mapped('active'),
            [True, True, True, True],
        )
        self.assertEqual(self.folder.folder_id, self.parent_folder,
            "The restored folder must be anchored to the parent it had")

    def test_folder_unlink(self):
        """ To unlink a folder should unlink all its descendant. """
        self.folder.unlink()
        self.assertEqual(self.folders.exists(), self.parent_folder,
            "Folder and Child Folder must have been deleted")
        self.assertFalse(self.document.exists())

    def test_folder_archive_unlink(self):
        """
        To unlink the last document of an archived folder should unlink
        that folder too.
        """
        self.folder.action_archive()
        self.document.unlink()
        self.assertEqual(
            self.folders.exists(), self.parent_folder, "Folder and Child Folder should have been deleted"
        )

    def test_folder_and_document_archive_unlink(self):
        """
        Test user should archive and unlink both document and folder once.
        """
        documents_to_remove = self.child_folder + self.document
        documents_to_remove.action_archive()
        documents_to_remove.unlink()

        self.assertFalse(documents_to_remove.exists())

    def test_folder_create_subfolder(self):
        self.folder.action_update_access_rights('view', 'edit', False, {
            self.user_portal.partner_id: ('view', None),
        })
        new_folder = self.env['documents.document'].create({
            'name': 'New Child Folder',
            'folder_id': self.folder.id,
        })
        self.assertEqual(new_folder.access_internal, 'view')
        self.assertEqual(new_folder.access_via_link, 'edit')
        self.assertFalse(new_folder.is_access_via_link_hidden)
        acl = new_folder.access_ids.ensure_one()
        self.assertEqual(acl.partner_id, self.user_portal.partner_id)
        self.assertEqual(acl.role, 'view')

    def test_folder_copy(self):
        self.folder.owner_id = self.user_portal
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            folder_copy = self.folder.copy()
        self.assertNotEqual(folder_copy.id, self.folder.id)
        self.assertEqual(folder_copy.name, f'{self.folder.name} (copy)')
        self.assertEqual(folder_copy.type, 'folder')
        self.assertEqual(folder_copy.folder_id, self.parent_folder)
        self.assertFalse(folder_copy.owner_id)

        folder_shortcut = self.folder.action_create_shortcut()
        self.assertNotEqual(folder_shortcut.id, self.folder.id)
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            folder_shortcut_copy = folder_shortcut.copy()
        self.assertNotEqual(folder_shortcut_copy.id, folder_shortcut.id)
        self.assertEqual(folder_shortcut_copy.name, f'{folder_shortcut.name} (copy)')

        child_copy = folder_copy.children_ids.ensure_one()
        self.assertNotEqual(child_copy.id, self.child_folder.id)
        self.assertEqual(child_copy.name, self.child_folder.name)
        self.assertEqual(child_copy.type, 'folder')
        self.assertEqual(child_copy.folder_id, folder_copy)
        self.assertFalse(child_copy.owner_id)

        document_copy = child_copy.children_ids.ensure_one()
        self.assertNotEqual(document_copy.id, self.document.id)
        self.assertEqual(document_copy.name, self.document.name)
        self.assertEqual(document_copy.type, 'binary')
        self.assertEqual(document_copy.folder_id, child_copy)
        self.assertFalse(child_copy.owner_id)

        attachment = document_copy.attachment_id.ensure_one()
        self.assertNotEqual(attachment.id, self.document.attachment_id.id)
        self.assertEqual(document_copy.raw, self.document.raw)

        # Check that owner is used for all children documents too
        folder_copy_2 = self.folder.copy({'owner_id': self.user_portal.id})
        self.assertEqual(folder_copy_2.owner_id, self.user_portal)
        self.assertEqual(folder_copy_2.children_ids.owner_id, self.user_portal)
        self.assertEqual(folder_copy_2.children_ids.children_ids.owner_id, self.user_portal)

    def test_folder_copy_embedded_actions(self):
        """Test that copying a folder embeds the same server actions"""
        original_folder = self.env['documents.document'].create({
            'type': 'folder',
            'name': 'A Folder',
            'children_ids': [Command.create({'name': "A Request"})]
        })
        original_child = original_folder.children_ids[0]
        self.assertFalse(original_folder.available_embedded_actions_ids)
        server_action = self.env['ir.actions.server'].create({
            'name': 'Send to Parent Folder',
            'model_id': self.env.ref('documents.model_documents_document').id,
            'type': 'ir.actions.server',
            'group_ids': self.env.ref('base.group_user').ids,
            'update_path': 'folder_id',
            'usage': 'documents_embedded',
            'state': 'object_write',
            'resource_ref': f'documents.document,{self.parent_folder.id}',
        })
        self.env['documents.document'].action_folder_embed_action(
            original_folder.id, server_action.id)
        original_child._compute_available_embedded_actions_ids()
        action_original_child = original_child.available_embedded_actions_ids

        self.assertEqual(len(action_original_child), 1)
        self.assertEqual(action_original_child.action_id.id, server_action.id)
        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            copied_folder = original_folder.copy()
        copied_child = copied_folder.children_ids[0]
        copied_child._compute_available_embedded_actions_ids()
        action_copied_child = copied_child.available_embedded_actions_ids
        self.assertEqual(len(action_copied_child), 1)
        self.assertEqual(action_original_child.action_id, action_copied_child.action_id)
        self.assertNotEqual(action_original_child, action_copied_child)

    def test_action_move_folder(self):
        self.document_manager, self.internal_user = self.env['res.users'].create([
            {
                'email': "dtdm@yourcompany.com",
                'group_ids': [Command.link(self.env.ref('documents.group_documents_manager').id)],
                'login': "dtdm",
                'name': "Documents Manager",
            },
            {
                'login': 'internal_user',
                'group_ids': [Command.link(self.env.ref('base.group_user').id)],
                'name': 'Internal user'
            }
        ])
        self.folder_cpy_1, self.folder_cpy_2, self.folder_cpy_3 = self.env['documents.document'].create(
            [{
                'access_internal': 'view',
                'folder_id': False,
                'name': f'COMPANY folder {i + 1}',
                'sequence': i,
                'type': 'folder',
                'owner_id': False}
                for i in range(3)])
        self.company_folders = self.folder_cpy_1 | self.folder_cpy_2 | self.folder_cpy_3

        # Moving folders in COMPANY
        for company_folder in self.company_folders:
            self.assertTrue(company_folder._is_company_root_folder())
            self.assertTrue(company_folder.with_user(self.document_manager).user_permission == 'edit')
            self.assertTrue(company_folder.with_user(self.internal_user).user_permission == 'view')

        self.assertTrue(self.folder_cpy_1.sequence < self.folder_cpy_2.sequence < self.folder_cpy_3.sequence)
        with self.assertRaises(AccessError):
            self.folder_cpy_1.with_user(self.internal_user).action_move_folder("COMPANY", self.folder_cpy_2.id)
        # Insert before a folder
        self.folder_cpy_3.with_user(self.document_manager).action_move_folder("COMPANY", self.folder_cpy_1.id)
        self.assertTrue(self.folder_cpy_3.sequence < self.folder_cpy_1.sequence < self.folder_cpy_2.sequence)
        # Move at the end
        self.folder_cpy_3.with_user(self.document_manager).action_move_folder("COMPANY", False)
        self.assertTrue(self.folder_cpy_3.sequence > self.folder_cpy_1.sequence)
        self.assertTrue(self.folder_cpy_3.sequence > self.folder_cpy_2.sequence)

        # Moving folders in MY DRIVE
        self.folder_my_1, self.folder_my_2, self.folder_my_3 = self.env['documents.document'].create([
            {
                'folder_id': False,
                'name': f"My Drive folder {i + 1}",
                'sequence': i,
                'type': 'folder',
                'owner_id': self.internal_user.id,
            }
            for i in range(3)])
        self.my_drive_folders = self.folder_my_1 | self.folder_my_2 | self.folder_my_3

        for my_drive_folder in self.my_drive_folders:
            self.assertTrue(my_drive_folder.with_user(self.document_manager).user_permission == 'none')
            self.assertTrue(my_drive_folder.with_user(self.internal_user).user_permission == 'edit')

        with self.assertRaises(AccessError):
            self.folder_my_2.with_user(self.document_manager).action_move_folder("MY", self.folder_my_1.id)

        # Insert before a folder
        self.folder_my_3.with_user(self.internal_user).action_move_folder("MY", self.folder_my_1.id)
        self.assertTrue(self.folder_my_3.sequence < self.folder_my_1.sequence < self.folder_my_2.sequence)
        # Move at the end
        self.folder_my_3.with_user(self.internal_user).action_move_folder("MY", False)
        self.assertTrue(self.folder_my_3.sequence > self.folder_my_1.sequence)
        self.assertTrue(self.folder_my_3.sequence > self.folder_my_2.sequence)
