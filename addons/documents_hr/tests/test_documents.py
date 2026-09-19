# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, RecordCapturer, tagged

from .test_documents_hr_common import TransactionCaseDocumentsHr


@tagged('post_install', '-at_install', 'test_document_bridge')
class TestCaseDocumentsBridgeHR(HttpCase, TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee (related to doc_user)',
            'user_id': cls.doc_user.id,
            'work_contact_id': cls.doc_user.partner_id.id,
            'wage': 1,
        })
        cls.contract = cls.employee.version_id

    def test_documents_hr_employees_folders_no_owner(self):
        # Document owner is the user that creates the document. But hr 'system' folders cannot be owned by anyone.
        public_user = self.env['res.users'].create({
            'name': 'Johnny Applicant',
            'login': 'applicant',
            'email': 'john.icant@example.com',
        })
        employee = self.env['hr.employee'].with_user(public_user).sudo().create({
            'name': 'Johnny Employee'
        })
        self.assertTrue(employee.hr_employee_folder_id)
        self.assertFalse(employee.hr_employee_folder_id.owner_id)

    def test_employee_subfolder_generation_renaming_and_access(self):
        # hr_employee_folder_id should have been created at employee creation
        self.assertEqual(self.employee.hr_employee_folder_id.name, self.employee.name,
                         "HR Employee Subfolder should have the same name as the employee.")
        self.employee.name = "Zator"
        self.assertEqual(self.employee.hr_employee_folder_id.name, "Zator",
                         "HR Employee Subfolder should be renamed when renaming the employee.")

        # Test on new Company - HR Employee folder should be created on company create.
        # and a new employee should generate a subfolder for that employee inside the company's HR Employee folder.
        new_company = self.env['res.company'].create({
            'name': 'New Company'
        })
        self.assertTrue(new_company.documents_employee_folder_id)
        new_company_employee = self.env['hr.employee'].create({
            'name': 'New Company Employee',
            'user_id': self.doc_user_2.id,
            'company_id': new_company.id
        })
        self.assertTrue(new_company_employee.hr_employee_folder_id)
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_via_link, 'edit')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_internal, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.folder_id, new_company.documents_employee_folder_id)
        # Test unconfigured companies: employees should not have a subfolder
        doc_employee_folder_id = new_company.documents_employee_folder_id.id
        new_company.documents_employee_folder_id = False
        new_company_employee_bis = self.env['hr.employee'].create({
            'name': 'New Company Employee Bis',
            'company_id': new_company.id
        })
        self.assertFalse(new_company_employee_bis.hr_employee_folder_id)
        # Reconfiguring the company should create employee subfolders for employee that has none
        new_company.documents_employee_folder_id = doc_employee_folder_id
        self.assertTrue(new_company_employee_bis.hr_employee_folder_id)
        self.assertEqual(new_company_employee_bis.hr_employee_folder_id.folder_id, new_company.documents_employee_folder_id)

        # Test changing settings for Documents HR Employee folder. All employee subfolders should follow.
        new_folder = self.env['documents.document'].create({
            'name': 'New folder',
            'type': 'folder'
        })
        self.env.company.documents_employee_folder_id = new_folder.id
        self.assertEqual(self.env.company.documents_employee_folder_id.access_via_link, 'none')
        self.assertEqual(self.env.company.documents_employee_folder_id.access_internal, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_via_link, 'edit')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_internal, 'none')
        self.assertEqual(self.employee.hr_employee_folder_id.folder_id.id, new_folder.id,
                         "Changing HR Employee folder target should be propagated to each employee subfolders.")
        self.assertEqual(self.employee.hr_employee_folder_id.access_via_link, 'edit')
        self.assertEqual(self.employee.hr_employee_folder_id.access_internal, 'none')

        # Check access - only used for HR users - even employee should not have access to their "own" subfolder
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.doc_user_2).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.employee.user_id).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.employee.user_id).write({'name': "Test"})
        # Hr manager have access because added as edit member
        self.employee.hr_employee_folder_id.with_user(self.hr_manager).read(['name'])
        self.employee.hr_employee_folder_id.with_user(self.hr_manager).write({'name': "Test2"})
        self.employee.hr_employee_folder_id.access_ids = False
        # Hr user and HR manager should be able to view and edit but only using the access token
        # see @test_open_document_from_hr test method - If access to smart button and action, access to the records.
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_manager).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_user).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_manager).write({'name': "Test2"})
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_user).write({'name': "Test"})

    def test_bridge_hr_settings_on_write(self):
        """
        Makes sure the settings apply their values when an ir_attachment is set as message_main_attachment_id
        on invoices.
        """
        attachment_txt_test = self.env['ir.attachment'].create({
            'datas': self.TEXT,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': 'hr.employee',
            'res_id': self.employee.id,
        })

        document = self.env['documents.document'].search([('attachment_id', '=', attachment_txt_test.id)])
        self.assertTrue(document.exists(), "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertEqual(document.partner_id, self.employee.work_contact_id, "The partner_id should be the employee's address")
        self.assertEqual(document.access_via_link, "none")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)

    def test_upload_employee_attachment(self):
        """
        Make sure an employee's attachment is linked to the existing document
        and a new one is not created.
        """
        document = self.env['documents.document'].create({
            'name': 'Doc',
            'folder_id': self.employee.hr_employee_folder_id.id,
            'res_model': self.employee._name,
            'res_id': self.employee.id,
        })
        document.write({
            'datas': self.TEXT,
            'mimetype': 'text/plain',
        })
        self.assertTrue(document.attachment_id, "An attachment should have been created")

    def test_hr_employee_document_auto_created_not_shared_with_employee(self):
        """ Test that automatically created employee documents from attachment are not shared with the employee. """
        attachment = self.env['ir.attachment'].create({
            'name': 'test.txt',
            'mimetype': 'text/plain',
            'datas': self.TEXT,
            'res_model': 'hr.employee',
            'res_id': self.employee.id,
        })
        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document)
        self.assertEqual(document.with_user(self.employee.user_id).user_permission, 'none')

    def test_hr_employee_document_upload_not_shared_with_employee(self):
        """Test that uploaded hr.employee documents are not shared with the employee."""
        self.authenticate(self.hr_manager.login, self.hr_manager.login)
        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{self.employee.hr_employee_folder_id.access_token}',
                data={
                    'csrf_token': http.Request.csrf_token(self),
                    'res_id': self.employee.id,
                    'res_model': 'hr.employee',
                },
                files={'ufile': ('hello.txt', b"Hello", 'text/plain')},
            )
            res.raise_for_status()
        document = capture.records.ensure_one()
        self.assertEqual(document.res_model, "hr.employee",
                         "The uploaded document is linked to the employee model")
        self.assertEqual(document.res_id, self.employee.id,
                         "The uploaded document is linked to the employee record")
        self.assertEqual(document.with_user(self.doc_user).user_permission, "none",
                         "The employee has no access to the uploaded document")
        self.assertEqual(document.with_user(self.hr_manager).user_permission, "edit",
                         "The HR manager has access to the uploaded document")

    def test_open_document_from_hr(self):
        """ Test that opening the document app from an employee (hr app) is opening only for hr users. """
        with self.assertRaises(AccessError):
            self.employee.with_user(self.doc_user_2).action_open_documents()
        action = self.employee.with_user(self.hr_user).action_open_documents()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'].split('/')[-1], self.employee.hr_employee_folder_id.access_token)

    def test_raise_if_used_folder(self):
        """It shouldn't be possible to archive/delete a folder used by a company (see _unlink_except_company_folders)"""
        company_b = self.env['res.company'].create({'name': 'Company B'})
        root = self.env['documents.document'].create({'name': 'root', 'type': 'folder', 'access_internal': 'edit'})
        folder_parent = self.env['documents.document'].create(
            {'name': 'parent', 'type': 'folder', 'folder_id': root.id})
        folder_hr_employees2 = self.env['documents.document'].create({
            'name': 'Employees -  company 2', 'type': 'folder', 'folder_id': folder_parent.id, 'access_internal': 'none'})
        company_b.documents_employee_folder_id = folder_hr_employees2
        company_b.documents_hr_settings = False

        self.assertEqual(folder_parent.with_user(self.doc_user).user_permission, 'edit')
        self.assertEqual(folder_hr_employees2.with_user(self.doc_user).user_permission, 'none')
        # It should be possible to archive an unused 'HR' folder"
        with self.assertRaises(UserError,
                               msg="It should not be possible for non admin to archive the 'HR Employee' folder"):
            folder_hr_employees2.with_user(self.doc_user).action_archive()
        folder_hr_employees2.action_archive()
        folder_hr_employees2.action_unarchive()
        company_b.documents_hr_settings = True

        with self.assertRaises(UserError,
                               msg="It should not be possible to archive an used 'HR Employee' folder"):
            folder_hr_employees2.action_archive()
        with self.assertRaises(UserError,
                               msg="It should not be possible to archive an ancestor of the used 'HR' folder"):
            folder_parent.action_archive()
        with self.assertRaises(UserError,
                               msg="It should not be possible to unlink a 'HR Employee' folder"):
            folder_hr_employees2.unlink()
        with self.assertRaises(UserError,
                               msg="It should not be possible to delete an ancestor of the 'HR' folder"):
            folder_parent.unlink()
        self.assertTrue(folder_parent.exists())
        self.assertTrue(folder_hr_employees2.exists())

        with self.assertRaises(UserError,
                               msg="It should not be possible to delete an employee subfolder of the 'HR' Employee folder"):
            self.employee.hr_employee_folder_id.unlink()

    def test_portal_user_own_root_documents(self):
        """ Portal user (linked to employee!!) should be able to own root
        documents as they are now allowed to be set as employee related user
        and employee documents are store in their "my drive", and are,
        by definition, root documents"""
        employee_portal_user, normal_portal_user = self.env['res.users'].create([{
            'name': "Employee Portal User",
            'login': "employee_portal",
            'email': "employee_portal@yourcompany.com",
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]
        }, {
            'name': "Normal Portal User",
            'login': "normal_portal",
            'email': "normal_portal@yourcompany.com",
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]
        }])
        self.employee.user_id = employee_portal_user
        self.env['documents.document'].create({
            'name': 'test',
            'folder_id': False,
            'owner_id': employee_portal_user.id
        })
        with self.assertRaises(ValidationError, msg="Portal users that are not linked to an employee cannot own root documents."):
            self.env['documents.document'].create({
                'name': 'test',
                'folder_id': False,
                'owner_id': normal_portal_user.id
            })

    def test_contract_document_creation(self):
        attachment = self.env['ir.attachment'].create({
            'datas': self.TEXT,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': self.contract._name,
            'res_id': self.contract.id,
        })

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document.exists(), "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertEqual(document.partner_id, self.employee.work_contact_id, "The partner_id should be the employee's work contact")
        self.assertEqual(document.access_via_link, "none")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)

    def test_hr_contract_document_creation_permission_employee_only(self):
        """ Test that created hr.contract documents are only viewable by the employee and editable by hr managers. """
        self.check_document_creation_permission(self.contract)
