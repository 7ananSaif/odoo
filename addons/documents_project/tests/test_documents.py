# -*- coding: utf-8 -*-

import base64

from odoo.exceptions import UserError
from odoo.tests.common import users

from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.addons.project.tests.test_project_base import TestProjectCommon

GIF = b"R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="
TEXT = base64.b64encode(bytes("workflow bridge project", 'utf-8'))


class TestDocumentsBridgeProject(TestProjectCommon, TransactionCaseDocuments):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_txt_2 = cls.env['documents.document'].create({
            'datas': TEXT,
            'name': 'file2.txt',
            'mimetype': 'text/plain',
            'folder_id': cls.folder_a_a.id,
        })
        cls.pro_admin = cls.env['res.users'].create({
            'name': 'Project Admin',
            'login': 'proj_admin',
            'email': 'proj_admin@example.com',
            'group_ids': [(4, cls.env.ref('project.group_project_manager').id)],
        })

    def test_archive_folder_on_projects_unlinked(self):
        """
        Projects folders should be archived if every related projects have been unlinked.
        """
        folder_1, folder_2, folder_3, folder_4 = self.env['documents.document'].create(
            [{'name': f'F{i}', 'type': 'folder'} for i in range(4)]
        )

        (
            project_0, project_1, project_2, project_3,
            project_4, project_5, project_6, _,
        ) = self.env['project.project'].create([
            {'name': f'p{i}', 'documents_folder_id': folder.id}
            for i, folder in enumerate([folder_1] * 4 + [folder_2] * 3 + [folder_3])
        ])

        cases = [
            (
                project_1 | project_4,
                folder_1 | folder_2 | folder_3 | folder_4,
                self.env['documents.document']
            ), (
                project_2,
                folder_1 | folder_2 | folder_3 | folder_4,
                self.env['documents.document']
            ), (
                project_0 | project_3 | project_5 | project_6,
                folder_3 | folder_4,
                folder_1 | folder_2
            ),
        ]

        count_start = self.env['documents.document'].search_count([('active', '=', True)])

        for projects_to_unlink, active_folders, inactive_folders in cases:
            with self.subTest(projects_to_unlink=projects_to_unlink, active_folders=active_folders, inactive_folders=inactive_folders):
                projects_to_unlink.unlink()
                self.assertTrue(all(active_folders.mapped('active')))
                self.assertFalse(any(inactive_folders.mapped('active')))

        count_end = self.env['documents.document'].search_count([('active', '=', True)])
        self.assertEqual(count_end, count_start - 2)

    def test_bridge_parent_folder(self):
        """
        Tests the "Parent Folder" setting
        """
        parent_folder = self.env.company.documents_project_folder_id
        self.assertEqual(self.project_pigs.documents_folder_id.folder_id, parent_folder, "The folder of the project should be a child of the 'Projects' folder.")

    def test_project_folder_creation(self):
        project = self.env['project.project'].create({
            'name': 'Project',
        })
        self.assertTrue(project.documents_folder_id, "A folder should be created for the project")

    def test_project_task_access_document(self):
        """
        Tests that 'MissingRecord' error should not be raised when trying to switch
        folder for a non-existing document.

        - The 'active_id' here is the 'id' of a non-existing document.
        - We then try to access 'All' folder by calling the 'search_panel_select_range'
            method. We should be able to access the folder.
        """
        missing_id = self.env['documents.document'].search([], order='id DESC', limit=1).id + 1
        result = self.env['documents.document'].with_context(
            active_id=missing_id, active_model='project.task').search_panel_select_range('user_folder_id')
        self.assertTrue(result)

    def test_copy_project(self):
        """
        When duplicating a project, there should be exactly one copy of the folder linked to the project.
        If there is the `no_create_folder` context key, then the folder should not be copied (note that in normal flows,
        when this context key is used, it is expected that a folder will be copied/created manually, so that we don't
        end up with a project having the documents feature enabled but no folder).
        """
        last_folder_id = self.env['documents.document'].search([('type', '=', 'folder')], order='id desc', limit=1).id
        self.project_pigs.copy()
        new_folder = self.env['documents.document'].search([('type', '=', 'folder'), ('id', '>', last_folder_id)])
        self.assertEqual(len(new_folder), 1, "There should only be one new folder created.")
        self.project_goats.with_context(no_create_folder=True).copy()
        self.assertEqual(self.env['documents.document'].search_count(
            [('type', '=', 'folder'), ('id', '>', new_folder.id)], limit=1),
            0,
            "There should be no new folder created."
        )

    @users('proj_admin')
    def test_rename_project(self):
        """
        When renaming a project, the corresponding folder should be renamed as well.
        Even when the user does not have write access on the folder, the project should be able to rename it.
        """
        new_name = 'New Name'
        self.project_pigs.with_user(self.env.user).name = new_name
        self.assertEqual(self.project_pigs.documents_folder_id.name, new_name, "The folder should have been renamed along with the project.")

    def test_delete_project_folder(self):
        """
        It should not be possible to delete the "Projects" folder.
        """
        project_folder = self.env.ref('documents_project.document_project_folder')
        with self.assertRaises(UserError, msg="It should not be possible to delete the 'Projects' folder"):
            project_folder.unlink()

        current = project_folder
        for i in range(3):
            current.folder_id = self.env['documents.document'].create({
                "name": f"Ancestor Test {i}",
                "type": "folder",
            })
            current = current.folder_id

        with self.assertRaises(UserError, msg="It should not be possible to delete an ancestor of the 'Projects' folder"):
            current.unlink()

        # But it shouldn't interfere with legit deletion/archiving
        project_folder.action_update_access_rights(
            access_internal='none', access_via_link='none',
            partners={self.doc_user.partner_id.id: (False, False)})
        project_folder.invalidate_recordset(fnames=['parent_path'])
        self.document_txt.with_user(self.doc_user).action_archive()
        self.assertFalse(self.document_txt.active)
        self.document_txt.with_user(self.doc_user).unlink()
        self.assertFalse(self.document_txt.exists())

    def test_changing_project_folder_moves_documents(self):
        """
        When a project folder changes, move documents.
        """
        project = self.env['project.project'].create({'name': 'Project'})
        project_document, other_folder = self.env['documents.document'].create([{
            'name': 'Test project request',
            'folder_id':  project.documents_folder_id.id,
        }, {
            'name': 'Other Folder',
            'type': 'folder',
            'folder_id': self.env.ref('documents_project.document_project_folder').id,
        }])
        project.invalidate_recordset()
        self.assertEqual(project_document, project.document_ids)
        project.documents_folder_id = other_folder
        self.assertEqual(project_document.folder_id, other_folder)
        self.assertEqual(project_document, project.document_ids)

    def test_delete_folder_used_by_project(self):
        """
        It shouldn't be possible to delete a folder that is used by one or multiple projects.
        """
        project = self.env['project.project'].create({
            'name': "Test",
        })
        with self.assertRaises(UserError):
            project.documents_folder_id.unlink()

        project_1, project_2, project_3 = self.env['project.project'].create([{
            'name': f"Test Project {i}",
        } for i in range(3)])
        project_2.documents_folder_id = project_3.documents_folder_id
        (project_1 | project_2).documents_folder_id.folder_id = parent_folder = self.env['documents.document'].create({
            'name': "Test Folder",
            'type': 'folder',
        })
        with self.assertRaises(UserError, msg="It shouldn't be possible to delete a folder that is used by one or multiple projects."):
            parent_folder.unlink()

    def test_add_attachment_to_project_folder_id(self):
        project = self.env['project.project'].create({'name': "Test Project"})
        self.assertTrue(project.documents_folder_id)
        task = self.env['project.task'].create({'name': "Test Task", 'project_id': project.id})
        project_attachment, task_attachment = self.env['ir.attachment'].create([
            {"name": "project_image.png", "datas": GIF, "res_model": "project.project", "res_id": project.id},
            {"name": "task_image.png", "datas": GIF, "res_model": "project.task", "res_id": task.id},
        ])
        for attachment in (project_attachment, task_attachment):
            self.assertEqual(attachment.get_documents_operation_add_destination(), {
                'destination': str(project.documents_folder_id.id),
                'display_name': project.documents_folder_id.display_name,
            })

    def test_project_copy_includes_linked_documents(self):
        """
        Test that copying a project also copies its linked document.
        Steps:
        1. Link a document to the project (set folder and res_id).
        2. Copy the project.
        3. Check that the copied project has one linked document.
        """
        self.document_txt_2.write({
            'folder_id': self.project_pigs.documents_folder_id.id,
            'res_id': self.project_pigs.id,
        })
        copied_project_documents = self.project_pigs.copy().document_ids
        self.assertEqual(
            len(copied_project_documents), 1,
            "The copied project should have one document copied."
        )
