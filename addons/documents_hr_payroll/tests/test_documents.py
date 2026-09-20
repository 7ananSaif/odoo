# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.addons.documents.tests.test_documents_multipage import single_page_pdf
from odoo.addons.documents_hr.tests.test_documents_hr_common import TransactionCaseDocumentsHr
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import tagged


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeHR(TestPayslipBase, TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_us.ids))
        cls.env.user.company_id = cls.env.company.id

        cls.payroll_manager = cls.env['res.users'].create({
            'name': "Hr payroll manager test",
            'login': "hr_payroll_manager_test",
            'email': "hr_payroll_manager_test@yourcompany.com",
            'group_ids': [(6, 0, [cls.env.ref('hr_payroll.group_hr_payroll_user').id])]
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee (related to doc_user_2)',
            'user_id': cls.doc_user_2.id,
            'work_contact_id': cls.doc_user_2.partner_id.id
        })
        cls.richard_emp.user_id = cls.doc_user
        cls.contract = cls.richard_emp.version_ids[0]
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract.id,
        })

    def test_payslip_document_creation(self):
        # Set a different partner for the work_contact_id to verify that the partner of the employee user is used
        self.richard_emp.work_contact_id = self.doc_user.partner_id.copy()

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()

        attachment = self.env['ir.attachment'].search([('res_model', '=', self.payslip._name), ('res_id', '=', self.payslip.id)])
        self.assertTrue(attachment, "Validating a payslip should have created an attachment")

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document, "There should be a new document created from the attachment")
        self.assertEqual(document.owner_id, self.richard_emp.user_id)
        self.assertEqual(document.partner_id, self.richard_emp.user_id.partner_id, "The document contact must be the user partner of the employee")
        self.assertFalse(document.folder_id, "The document should have been created in the employee's My Drive")
        self.assertEqual(document.access_via_link, "view")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)
        # Only one access record, with the owner's partner. No one else than the employee itself should have access to the document.
        self.assertEqual(
            {a.partner_id: a.role for a in document.access_ids},
            {self.richard_emp.user_id.partner_id: False},  # False because owner (see _prepare_create_values @documents/../documents_document.py)
            "Only the employee should have access (write)"
        )
        self.assertEqual(document.with_user(self.richard_emp.user_id).user_permission, 'edit')  # Edit because owner
        self.check_document_no_access(document, self.doc_user_2)
        self.check_document_no_access(document, self.document_manager)
        self.check_document_no_access(document, self.payroll_manager)

    def test_hr_payroll_employee_declaration_document_creation_simple(self):
        """Check that the employee is the owner of the declarations and that nobody else has access."""
        declaration = self.env['hr.payroll.employee.declaration'].create({
            'res_model': 'hr.payslip',
            'res_id': self.payslip.id,
            'employee_id': self.employee.id,
            'pdf_file': single_page_pdf,
            'pdf_filename': 'Test Declaration.pdf',
            'state': 'pdf_to_post',
        })

        # add required hr.payroll.declaration.mixin methods
        with patch.object(
            self.env['hr.payslip'].pool['hr.payslip'],
            "_get_posted_mail_template",
            lambda s: self.env.ref('documents_hr_payroll.mail_template_new_declaration',
                                   raise_if_not_found=False),
            create=True
        ), patch.object(
            self.env['hr.payslip'].pool['hr.payslip'],
            "_get_posted_document_owner",
            lambda _s, employee: employee.user_id,
            create=True
        ):
            declaration._post_pdf()

        document = declaration.document_id
        self.assertEqual(document.name, 'Test Declaration.pdf')
        self.assertEqual(document.owner_id, self.employee.user_id)
        self.assertFalse(document.folder_id, "The document should have been created in the employee's My Drive")
        self.assertEqual(
            set(document.access_ids.mapped(lambda a: (a.partner_id, a.role))),
            {(self.employee.user_partner_id, False)}
        )
        self.assertEqual(document.access_via_link, "view")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)
        self.check_document_no_access(document, self.doc_user)
        self.check_document_no_access(document, self.document_manager)
        self.check_document_no_access(document, self.payroll_manager)

    def test_hr_payroll_documents_employee_without_user(self):
        employee_partner = self.env['res.partner'].create({
            'name': 'partner'
        })
        self.richard_emp.user_id = False
        self.richard_emp.work_contact_id = employee_partner.id

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()

        attachment = self.env['ir.attachment'].search(
            [('res_model', '=', self.payslip._name), ('res_id', '=', self.payslip.id)])
        self.assertTrue(attachment, "Validating a payslip should have created an attachment")

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document, "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertEqual(document.partner_id, self.richard_emp.work_contact_id,
                         "The document contact must be the user partner of the employee")
        self.assertEqual(document.folder_id, self.richard_emp.company_id.worker_payroll_folder_id, "The document should have been created in the company Workers Payroll folder")
        self.assertEqual(document.access_via_link, "view")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)
        # Only one access record, with the owner's partner. No one else than the employee itself should have access to the document.
        self.assertEqual(
            {a.partner_id: a.role for a in document.access_ids},
            {self.richard_emp.work_contact_id: 'view'},
            "Only the super admin should have access"
        )
        self.assertEqual(document.with_user(self.richard_emp.user_id).user_permission, 'edit')  # Edit because owner
        self.check_document_no_access(document, self.doc_user_2)
        self.check_document_no_access(document, self.document_manager)
        self.check_document_no_access(document, self.payroll_manager)

    def test_payslip_document_creation_with_no_partner(self):
        """Check that the payslip document is created when the employee has no partner."""
        # Ensure the employee has no partner
        self.richard_emp.user_id = False
        self.richard_emp.user_id.partner_id = False
        self.richard_emp.work_contact_id = False

        payslip = self.payslip
        payslip.compute_sheet()
        payslip.with_context(payslip_generate_pdf=True).action_payslip_done()
        self.assertTrue(payslip.queued_for_pdf, "Payslip should be queued for PDF generation when not generating directly.")

        payslip.browse()._cron_generate_pdf()

        # Check if the document is created
        document = self.env['documents.document'].search([('res_model', '=', payslip._name), ('res_id', '=', payslip.id)])
        self.assertFalse(document, "A document will not be created if the employee has no partner.")
