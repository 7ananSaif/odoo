from freezegun import freeze_time
from datetime import date, timedelta


import odoo.tests
import base64
from odoo.tools import file_open


@odoo.tests.tagged('-at_install', 'post_install', 'salary')
class TestEmployeeSalaryConfigurator(odoo.tests.HttpCase):
    @classmethod
    @freeze_time('2022-01-01 09:00:00')
    def setUpClass(cls):
        super().setUpClass()

        with file_open('hr_contract_salary/static/src/demo/employee_contract.pdf', "rb") as f:
            cls.pdf_content = f.read()

        attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': cls.pdf_content,
            'name': 'test_employee_contract.pdf',
        })

        cls.template = cls.env['sign.template'].create({})

        cls.document_id = cls.env['sign.document'].create({
            'attachment_id': attachment.id,
            'template_id': cls.template.id,
        })

        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'employee_id.name',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_date').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.707,
                'posY': 0.158,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_city',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.506,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_country_id.name',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.663,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'name': 'private_street',
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 1,
                'posX': 0.349,
                'posY': 0.184,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_job_responsible').id,
                'page': 2,
                'posX': 0.333,
                'posY': 0.575,
                'document_id': cls.document_id.id,
                'width': 0.200,
                'height': 0.050,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 2,
                'posX': 0.333,
                'posY': 0.665,
                'document_id': cls.document_id.id,
                'width': 0.200,
                'height': 0.050,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_date').id,
                'name': False,
                'required': True,
                'responsible_id': cls.env.ref('hr_sign.sign_item_role_employee_signatory').id,
                'page': 2,
                'posX': 0.665,
                'posY': 0.694,
                'document_id': cls.document_id.id,
                'width': 0.150,
                'height': 0.015,
            }
        ])

        cls.company_id = cls.env['res.company'].create({
            'name': 'Rambo Company - TEST',
            'country_id': cls.env.ref('base.be').id,
        })

        with file_open('sign/static/demo/signature.png', "rb") as f:
            img_content = base64.b64encode(f.read())

        cls.env.ref('base.user_admin').write({
            'company_ids': [(4, cls.company_id.id)],
            'company_id': cls.company_id.id,
            'name': 'Mitchell Admin',
            'sign_signature': img_content,
        })
        cls.env.ref('base.user_admin').partner_id.write({
            'email': 'mitchell.stephen@example.com',
            'name': 'Mitchell Admin',
            'street': '215 Vine St',
            'city': 'Scranton',
            'zip': '18503',
            'country_id': cls.env.ref('base.us').id,
            'state_id': cls.env.ref('base.state_us_39').id,
            'phone': '+1 555-555-5555',
            'tz': 'Europe/Brussels',
            'company_id': cls.company_id.id,
        })
        cls.env.ref('base.main_partner').email = "info@yourcompany.example.com"

        cls.senior_dev_contract = cls.env['hr.version'].create({
            'name': 'Senior Developer Template Contract',
            'wage': 6000,
            'structure_type_id': cls.env.ref('hr.structure_type_employee').id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'company_id': cls.company_id.id,
        })

        cls.job = cls.env['hr.job'].create({
            'name': 'Senior Developer BE',
            'company_id': cls.company_id.id,
            'contract_template_id': cls.senior_dev_contract.id,
            'user_id': cls.env.ref('base.user_admin').id,
        })

        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Ahmed Abdelrazek',
            'date_version': date(2020, 1, 1),
            'contract_date_start': date(2020, 1, 1),
            'contract_date_end': False,
            'company_id': cls.company_id.id,
            'job_id': cls.job.id,
            'sign_template_id': cls.template.id,
            'contract_update_template_id': cls.template.id,
            'hr_responsible_id': cls.env.ref('base.user_admin').id,
            'work_email': 'ahmed.abdelrazek@test_email.com',

        })

    def test_employee_salary_configurator_flow(self):
        employee = self.env['hr.employee'].search([('name', 'ilike', 'Ahmed Abdelrazek')])
        active_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', True)])
        self.assertEqual(len(active_versions), 1)
        self.assertEqual(active_versions[0].contract_date_start, date(2020, 1, 1))
        self.assertFalse(active_versions[0].contract_date_end)
        with freeze_time("2022-01-01 12:00:00"):
            self.start_tour("/", 'hr_contract_salary_employee_flow_tour', login='admin', timeout=350)
            self.assertEqual(len(active_versions), 1)
            self.assertFalse(active_versions[0].contract_date_end)
        with freeze_time("2022-01-01 13:00:00"):
            self.start_tour("/", 'hr_contract_salary_employee_flow_tour_counter_sign', login='admin', timeout=350)
            active_versions = self.env['hr.version'].search([('employee_id', '=', employee.id), ('active', '=', True)])
            self.assertEqual(len(active_versions), 2)
            self.assertEqual(active_versions[0].contract_date_end, active_versions[-1].contract_date_start - timedelta(days=1))
