from odoo import Command
from odoo.tools import file_open
from odoo.tests.common import TransactionCase, new_test_user


class TestSignRequestCancel(TransactionCase):

    def setUp(cls):
        super().setUp()

        with file_open('hr_contract_salary/static/src/demo/employee_contract.pdf', "rb") as f:
            pdf_content = f.read()

        cls.attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': pdf_content,
            'name': 'test_employee_contract.pdf',
        })

        cls.template_id = cls.env['sign.template'].create({
            'name': 'Employee Contract Template',
        })

        cls.document_id = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_id.id,
        })

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'struct'})
        cls.job = cls.env['hr.job'].create({'name': 'Software Developer'})
        cls.contract_template = cls.env['hr.version'].create({
            'name': "Contract Template",
            'wage': 6500,
            'structure_type_id': cls.structure_type.id,
            'job_id': cls.job.id,
        })

        cls.sign_item = cls.env['sign.item'].create([{
            'type_id': cls.env.ref('sign.sign_item_type_text').id,
            'required': True,
            'responsible_id': cls.env.ref('hr_sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'document_id': cls.document_id.id,
            'width': 0.150,
            'height': 0.015,
        }])

        cls.partner = cls.env['res.partner'].create({'name': 'Employee', 'email': 'employee@example.com'})

        cls.salary_offer = cls.env['hr.contract.salary.offer'].create({
            'contract_template_id': cls.contract_template.id,
        })

    def test_cancel_sign_request(self):
        new_test_user(self.env, login='user1', groups='sign.group_sign_user')
        with self.with_user("user1"):
            # sudo() to avoid recreating everything again and instead use already present record
            template_id = self.env['sign.template'].sudo().create({
                'name': 'Employee Contract Template(1)',
            })
            self.env['sign.document'].sudo().create({
                'template_id': template_id.id,
                'attachment_id': self.attachment.id,
                'sign_item_ids': self.sign_item
            })
            sign_request = self.env['sign.request'].create({
                'template_id': template_id.id,
                'reference': 'Test Offer',
                'request_item_ids': [Command.create({
                    'partner_id': self.partner.id,
                    'role_id': self.env.ref('hr_sign.sign_item_role_default').id,
                })],
            })
        self.salary_offer.sign_request_ids = sign_request

        with self.with_user("user1"):
            sign_request.cancel()
            self.assertEqual(sign_request.state, 'canceled', "User should be able to cancel his Sign Request.")
        self.assertEqual(self.salary_offer.state, 'cancelled', "The offer should be cancelled when the sign request is cancelled.")
