# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, time
from odoo.tests import common


class TestPayslipBase(common.TransactionCase):

    def setUp(self):
        super(TestPayslipBase, self).setUp()
        self.env.company.country_id = self.env.ref('base.be')
        self.employee = self.env['hr.employee'].create({
            'name': 'employee',
            'date_version': '2019-01-01',
            'contract_date_start': '2019-01-01',
        })
        self.version = self.employee.version_id

    def check_payslip(self, name, payslip, values):
        for code, value in values.items():
            self.assertAlmostEqual(payslip.line_ids.filtered(lambda line: line.code == code).total, value)

    def update_version(self, date_start, date_end=False, wage=2500):
        self.version.write({
            'wage': wage,
            'wage_on_signature': wage,
            'employee_id': self.employee.id,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            'date_version': date_start,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'internet': False,
            'mobile': False,
        })
        return self.version

    def create_version(self, date_start, date_end=False, wage=2500):
        return self.employee.create_version({
            'wage': wage,
            'wage_on_signature': wage,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            'date_version': date_start,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'internet': False,
            'mobile': False,
        })

    def create_payslip(self, structure, date_start, date_end=False):
        return self.env['hr.payslip'].create({
            'name': '%s for %s' % (structure, self.employee),
            'employee_id': self.employee.id,
            'date_from': date_start,
            'date_to': date_end,
            'struct_id': structure.id,
            'version_id': self.version.id,
        })
