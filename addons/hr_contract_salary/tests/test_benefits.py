# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from unittest.mock import patch

from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.addons.hr_contract_salary.models.hr_version import HrVersion


@tagged('benefits')
class TestBenefits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'struct'})
        cls.employee = cls.env['hr.employee'].create({
            'name': "John",
            'wage': 6500,
            'structure_type_id': cls.structure_type.id,
        })
        cls.version = cls.employee.version_id

    def test_yearly_cost_new_benefit(self):
        fieldname = 'x_test_field'
        model = self.env.ref('hr.model_hr_version')
        field = self.env['ir.model.fields'].create({
            'name': fieldname,
            'model': model.name,
            'ttype': 'float',
            'model_id': model.id,
        })
        self.version.write({fieldname: 50})
        self.assertEqual(self.version.final_yearly_costs, 12 * self.version.wage)
        benefit_costs = HrVersion._get_benefits_costs
        with patch.object(HrVersion, '_get_benefits_costs', lambda self: benefit_costs(self) + self[fieldname]):
            atype = self.env['hr.contract.salary.benefit.type'].create({})
            self.env['hr.contract.salary.benefit'].create({
                'benefit_type_id': atype.id,
                'res_field_id': field.id,
                'cost_res_field_id': field.id,
                'structure_type_id': self.structure_type.id,
            })
        self.assertEqual(self.version.final_yearly_costs, 12 * (self.version.wage + 50), "The new benefit should have updated the yearly cost")

    def test_holidays_yearly_cost(self):
        # yearly cost should not change even if the number of extra time off changes
        with patch.object(HrVersion, '_get_benefits_costs', lambda self: 250):
            self.version._compute_final_yearly_costs()
            base_yearly_cost = self.version.final_yearly_costs
            self.version.holidays = 15
            # this is triggered when configuring/signing a version
            # and recomputes the final_yearly_costs field
            self.version.wage_with_holidays = 6076.57
            self.assertAlmostEqual(base_yearly_cost, self.version.final_yearly_costs, 2,
                'Yearly costs should stay the same')

    def test_final_yearly_costs(self):
        # Yearly costs should not change when set manually on the interface
        # 100000 € / 12 = 8333.33333333
        # Wage is rounded, then 8333.33 * 12 = 99999.96
        self.version.final_yearly_costs = 100000
        self.version._onchange_final_yearly_costs()
        self.assertAlmostEqual(self.version.final_yearly_costs, 100000, 2)  # And not 99999.96

        self.version.holidays = 10
        self.version.final_yearly_costs = 100000
        self.version._onchange_final_yearly_costs()
        self.version._onchange_wage_with_holidays()
        self.assertAlmostEqual(self.version.final_yearly_costs, 100000, 2)  # And not 99999.96


@tagged('-at_install', 'post_install')
class TestInformationUpdate(HttpCase):

    @mute_logger('odoo.http')
    def test_prevent_update_employee_information(self):
        # Create an offer for an employee
        job = self.env['hr.job'].create({'name': 'Test job'})
        employee = self.env['hr.employee'].create({
            'email': 'test_employee@test.example.com',
            'name': 'Test Employee',
            'work_email': 'test_employee@test.example.com',
            'job_id': job.id,
            'wage': 1000,
        })
        internal_user = self.env['res.users'].create({'name': 'Cool User', 'login': 'cool_user'})
        employee.user_id = internal_user

        contract_employee = employee.version_id
        contract_template = self.env['hr.version'].create({
            'job_id': job.id,
            'name': "Test Template job",
            'wage': 1000,
        })
        salary_offer = self.env['hr.contract.salary.offer'].create([
            {
                'contract_template_id': contract_template.id,
                'employee_version_id': contract_employee.id,
                'employee_id': contract_employee.employee_id.id,
            }
        ])

        data = {
            "params": {
                "version_id": None,
                "offer_id": salary_offer.id,
                "benefits": {
                    'version': {
                        'wage': 1000,
                        'final_yearly_costs': 1000,
                    },
                    'version_personal': {},
                    'employee': {
                        'name': 'Edited Test Employee',
                        'private_email': 'edited_test_employee@test.example.com',
                        'employee_job_id': None,
                        'department_id': None,
                        'job_title': None,
                    },
                    'address': {},
                    'bank_account': {},
                },
            },
        }

        # Public user cannot update information via an offer linked to an existing employee with user
        res = self.url_open("/salary_package/submit", json=data)
        content = json.loads(res.content)
        self.assertIn('error', content)
        self.assertIn('AccessError', content['error']['data']['name'])
