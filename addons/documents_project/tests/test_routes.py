import io
import json
import zipfile

from odoo import http

from odoo.addons.project.tests.test_project_base import TestProjectCommon
from odoo.tests.common import HttpCase, RecordCapturer


class TestDocumentsProjectRoutes(HttpCase, TestProjectCommon):

    def test_upload_attachment_to_task_through_activity_with_folder(self):
        """Test the flow of uploading an attachment on a task through an activity with a folder.
        Ensure that only one document is created and ends up in the right folder.
        """
        activity_type = self.env["mail.activity.type"].create(
            {
                "name": "Upload Document with Folder",
                "category": "upload_file",
                "folder_id": self.project_pigs.documents_folder_id.id,
            }
        )
        activity = self.task_1.activity_schedule(
            activity_type_id=activity_type.id,
            user_id=self.env.user.id,
        )

        # Check that the activity is linked to the task
        self.assertEqual(
            activity.id,
            self.task_1.activity_ids.id,
            "Activity should be linked to the task",
        )

        # Check that a temporary document is created and linked to the activity
        document = self.env["documents.document"].search(
            [
                ("request_activity_id", "=", self.task_1.activity_ids.id),
                ("attachment_id", "=", False),
            ]
        )
        self.assertEqual(
            len(document), 1, "Temporary document should be linked on the activity"
        )

        # Upload an attachment through the activity
        self.authenticate("admin", "admin")
        with io.StringIO("Hello world!") as file:
            response = self.url_open(
                url="%s/mail/attachment/upload" % self.base_url(),
                files={"ufile": file},
                data={
                    "activity_id": activity.id,
                    "thread_id": self.task_1.id,
                    "thread_model": self.task_1._name,
                    "csrf_token": http.Request.csrf_token(self),
                },
            )
            self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)

        # Check that one document is now in the task's project
        self.assertEqual(
            self.task_1.project_id.document_ids.filtered(lambda d: d.type == "binary"),
            document,
            "Only document linked to the activity should be linked to the task",
        )
        attachment_id = response_content["data"]["attachment_id"]
        self.assertIn(attachment_id, [a["id"] for a in response_content["data"]["store_data"]["ir.attachment"]])
        activity._action_done(attachment_ids=[attachment_id])
        # Ensure the document is not linked to the activity anymore after the action is done
        self.assertFalse(
            document.request_activity_id,
            "Document should not be linked to the activity anymore",
        )

    def test_upload_document_propagates_values(self):
        """Check that relevant project-defined values are passed on documents uploaded inside the project folder."""
        self.project_pigs.partner_id = self.partner_1

        self.project_pigs.documents_folder_id.access_via_link = 'edit'
        self.authenticate(None, None)

        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{self.project_pigs.documents_folder_id.access_token}',
                                data={'csrf_token': http.Request.csrf_token(self)},
                                files={'ufile': ('hello.txt', b"Hello", 'text/plain')},
                                allow_redirects=False,
                                )
            res.raise_for_status()
        document = capture.records.ensure_one()
        self.assertEqual(document.partner_id, self.partner_1)

    def test_upload_to_project_folder_without_sharing_project(self):
        """Test sharing the project's folder without sharing the project itself.
        Ensure that the user can upload documents to the folder without having access to the project.
        Test Case:
        ==========
        1. Create a project
        2. Get shareable link for the project's folder with permission to upload
        3. as portal user, upload a document to the folder using the shareable link
        4. Verify that the document is created and linked to the folder
        """
        self.authenticate(self.user_portal.login, self.user_portal.login)

        folder = self.project_pigs.documents_folder_id
        folder.action_update_access_rights(
            partners={self.user_portal.partner_id: ('edit', False)},
            access_via_link='none'
        )

        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{folder.access_token}',
                data={'csrf_token': http.Request.csrf_token(self)},
                files={'ufile': ('hello.txt', io.BytesIO(b"Hello"), 'text/plain')},
                allow_redirects=False)
            res.raise_for_status()
        document = capture.records.ensure_one()
        self.assertEqual(document.name, 'hello.txt')
        self.assertEqual(document.mimetype, 'text/plain')
        self.assertEqual(document.folder_id, folder)
