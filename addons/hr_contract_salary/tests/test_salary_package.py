# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import Command
from odoo.tests.common import HttpCase, tagged
from odoo.tools import file_open, mute_logger


@tagged('-at_install', 'post_install')
class TestSalaryPackageItems(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'struct',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.default_contract = cls.env['hr.version'].create({
            'name': "Test Default Contract",
            'employee_id': False,
            'wage': 1000,
            'structure_type_id': cls.structure_type.id,
        })
        cls.job = cls.env['hr.job'].create({
            'name': 'Test job',
        })

        cls.company_id = cls.env['res.company'].create({
            'name': 'My Belgian Company - TEST',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.employee = cls.env['hr.employee'].create({
            'email': 'test_employee@test.example.com',
            'name': 'Test Employee',
            'work_email': 'test_employee@test.example.com',
            'job_id': cls.job.id,
            'company_id': cls.company_id.id,
        })
        cls.employee.user_id.write({
            'password': "employee_password",
            'partner_id': cls.env['res.partner'].create({
                'name': 'Laurie Poiret',
                'street': '58 rue des Wallons',
                'city': 'Louvain-la-Neuve',
                'zip': '1348',
                'country_id': cls.env.ref("base.be").id,
                'phone': '+0032476543210',
                'email': 'laurie.poiret@example.com',
                'company_id': cls.company_id.id,
            }).id,
            'company_id': cls.company_id.id,
            'company_ids': [Command.link(cls.company_id.id)],
        })

        with file_open('hr_contract_salary/static/src/demo/employee_contract.pdf', "rb") as f:
            cls.pdf_content = f.read()

        attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': cls.pdf_content,
            'name': 'test_employee_contract.pdf',
        })

        cls.template = cls.env['sign.template'].create({})
        cls.document = cls.env['sign.document'].create({
            'template_id': cls.template.id,
            'attachment_id': attachment.id,
            'sign_item_ids': [
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_text').id,
                    'name': 'employee_id.name',
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 1,
                    'posX': 0.273,
                    'posY': 0.158,
                    'width': 0.150,
                    'height': 0.015,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_date').id,
                    'name': False,
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 1,
                    'posX': 0.707,
                    'posY': 0.158,
                    'width': 0.150,
                    'height': 0.015,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_text').id,
                    'name': 'private_city',
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 1,
                    'posX': 0.506,
                    'posY': 0.184,
                    'width': 0.150,
                    'height': 0.015,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_text').id,
                    'name': 'private_country_id.name',
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 1,
                    'posX': 0.663,
                    'posY': 0.184,
                    'width': 0.150,
                    'height': 0.015,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_text').id,
                    'name': 'private_street',
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 1,
                    'posX': 0.349,
                    'posY': 0.184,
                    'width': 0.150,
                    'height': 0.015,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                    'name': False,
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_job_responsible').id,
                    'page': 2,
                    'posX': 0.333,
                    'posY': 0.575,
                    'width': 0.200,
                    'height': 0.050,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                    'name': False,
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 2,
                    'posX': 0.333,
                    'posY': 0.665,
                    'width': 0.200,
                    'height': 0.050,
                }),
                Command.create({
                    'type_id': cls.env.ref('sign.sign_item_type_date').id,
                    'name': False,
                    'required': True,
                    'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                    'page': 2,
                    'posX': 0.665,
                    'posY': 0.694,
                    'width': 0.150,
                    'height': 0.015,
                }),
            ]
        })

        cls.default_contract.contract_update_template_id = cls.template
        cls.default_contract.sign_template_id = cls.template
        cls.env.ref('base.user_admin').write({
            'email': 'mitchell.admin@example.com'
        })

    @mute_logger('odoo.http')
    def test_submit_salary_package(self):
        # Create an offer for an applicant
        contract = self.env['hr.version'].create({
            'name': "Test Contract",
            'wage': 1000,
            'structure_type_id': self.structure_type.id,
            'sign_template_id': self.template.id,
            'contract_update_template_id': self.template.id,
            'hr_responsible_id': self.env.ref('base.user_admin').id,
        })
        applicant = self.env["hr.applicant"].create({
            "partner_name": "Test Applicant",
            "email_from": "applicant@example.com",
        })
        salary_offer = self.env['hr.contract.salary.offer'].create([{
            'contract_template_id': self.default_contract.id,
            'employee_version_id': contract.id,
            'applicant_id': applicant.id,
            'sign_template_id': self.template.id,
            'access_token': '42' * 10,
            # 'employee_id': self.employee.id,
        }])

        data = {
            "params": {
                "offer_id": salary_offer.id,
                "benefits": {
                    'version': {
                        'wage': 1000,
                        'final_yearly_costs': 1000,
                    },
                    'version_personal': {
                        'private_city': "Louvain-La-Neuve",
                        'private_country_id': self.env.ref("base.be").id,
                        'private_street': "58 rue des Wallons",
                    },
                    'employee': {
                        'name': 'New Employee',
                        'private_email': 'new_employee@test.example.com',
                        'employee_job_id': None,
                        'department_id': None,
                        'job_title': None,
                    },
                    'address': {},
                    'bank_account': {},
                },
                "token": salary_offer.access_token,
            },
        }

        res = self.url_open("/salary_package/submit", json=data)
        content = json.loads(res.content)
        self.assertIn('result', content)

        request_id = self.env['sign.request'].browse(content['result']['request_id'])
        version = self.env['hr.version'].browse(content['result']['new_version_id'])
        self.assertTrue(request_id)
        self.assertTrue(version)
        self.assertEqual(version.private_city, "Louvain-La-Neuve")
        self.assertEqual(version.private_country_id.id, self.env.ref("base.be").id)
        self.assertEqual(version.private_street, "58 rue des Wallons")

        self.assertEqual(
            {
                item_value.sign_item_id.name: item_value.value
                for item_value in request_id.request_item_ids.sign_item_value_ids
            },
            {
                "employee_id.name": "New Employee",
                "private_city": "Louvain-La-Neuve",
                "private_country_id.name": "Belgium",
                "private_street": "58 rue des Wallons",
            },
        )

    @mute_logger('odoo.http')
    def test_submit_salary_package_employee(self):
        # Create an offer for an employee
        contract = self.employee.version_id
        salary_offer = self.env['hr.contract.salary.offer'].create([{
            'contract_template_id': self.default_contract.id,
            'employee_version_id': contract.id,
            'employee_id': contract.employee_id.id,
            'sign_template_id': self.template.id,
        }])
        self.employee.user_id = self.env['res.users'].create({
            'name': "foo",
            'login': "foo",
            'email': "foo@bar.com",
            'password': "foopassword",
        })

        data = {
            "params": {
                "version_id": None,
                "offer_id": salary_offer.id,
                "benefits": {
                    'version': {
                        'wage': 1000,
                        'final_yearly_costs': 1000,
                    },
                    'version_personal': {
                        'private_city': "Louvain-La-Neuve",
                        'private_country_id': self.env.ref("base.be").id,
                        'private_street': "58 rue des Wallons",
                    },
                    'employee': {
                        'name': 'New Employee',
                        'private_email': 'new_employee@test.example.com',
                        'employee_job_id': None,
                        'department_id': None,
                        'job_title': None,
                    },
                    'address': {},
                    'bank_account': {},
                },
            },
        }

        self.authenticate("foo", "foopassword")
        res = self.url_open("/salary_package/submit", json=data)
        content = json.loads(res.content)
        self.assertIn('result', content)

        request_id = self.env['sign.request'].browse(content['result']['request_id'])
        contract_id = self.env['hr.version'].browse(content['result']['new_version_id'])
        self.assertTrue(request_id)
        self.assertTrue(contract_id)
        self.assertEqual(contract_id.private_city, "Louvain-La-Neuve")
        self.assertEqual(contract_id.private_country_id.id, self.env.ref("base.be").id)
        self.assertEqual(contract_id.private_street, "58 rue des Wallons")

        self.assertEqual(
            {
                item_value.sign_item_id.name: item_value.value
                for item_value in request_id.request_item_ids.sign_item_value_ids
            },
            {
                "employee_id.name": "New Employee",
                "private_city": "Louvain-La-Neuve",
                "private_country_id.name": "Belgium",
                "private_street": "58 rue des Wallons",
            },
        )

    def test_sign_item_access(self):
        hradmin, hruser = self.env['res.users'].create([{
            'name': "foo",
            'login': "foo",
            'email': "foo@bar.com",
            'group_ids': [Command.set([self.env.ref('hr.group_hr_manager').id])],
        }, {
            'name': "bar",
            'login': "bar",
            'email': "bar@foo.com",
            'group_ids': [Command.set([
                self.env.ref('sign.group_sign_manager').id,
                self.env.ref('hr.group_hr_user').id,
            ])],
        }])

        HRSignItem = self.env['sign.item'].with_user(hradmin)
        UserSignItem = self.env['sign.item'].with_user(hruser)
        values = {
            'document_id': self.document.id,
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'required': True,
            'responsible_id': self.env.ref('hr_sign.sign_item_role_employee_signatory').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'width': 0.150,
            'height': 0.015,
        }

        self.template.user_id = hradmin
        # HR Manager only
        item = HRSignItem.create({'name': 'sign_template_signatories_ids.signatory', **values})
        self.assertEqual(item.name, 'sign_template_signatories_ids.signatory')

        # Field with a group
        item = HRSignItem.create({'name': 'contracts_count', **values})
        self.assertEqual(item.name, 'contracts_count')

        self.template.user_id = hruser
        # But regular users don't
        item = UserSignItem.create({'name': 'sign_template_signatories_ids.signatory', **values})
        self.assertEqual(item.name, '')

        # Accessible fields through an unaccessible model should not work
        item = UserSignItem.create({'name': 'sign_template_signatories_ids.partner_id.name', **values})
        self.assertEqual(item.name, '')

        # But access to normal fields should work
        item = UserSignItem.create({'name': 'name', **values})
        self.assertEqual(item.name, 'name')

        # Non-field should remain as-is
        item = UserSignItem.create({'name': 'Signature', **values})
        self.assertEqual(item.name, 'Signature')
