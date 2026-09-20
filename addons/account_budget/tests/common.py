# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.fields import Command


class TestAccountBudgetCommon(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ==== Products ====
        cls.product_a = cls.env['product.product'].create({
            'name': 'product_a',
            'standard_price': 100.0,
            'supplier_taxes_id': False
        })
        cls.product_b = cls.env['product.product'].create({
            'name': 'product_b',
            'standard_price': 100.0,
            'supplier_taxes_id': False
        })

        # ==== Analytic accounts ====

        cls.analytic_plan_projects = cls.env['account.analytic.plan'].create({'name': 'Projects'})
        cls.analytic_plan_departments = cls.env['account.analytic.plan'].create({'name': 'Departments test'})

        cls.project_column_name = cls.analytic_plan_projects._column_name()
        cls.department_column_name = cls.analytic_plan_departments._column_name()

        cls.analytic_account_partner_a = cls.env['account.analytic.account'].create({
            'name': 'analytic_account_partner_a',
            'partner_id': cls.partner_a.id,
            'plan_id': cls.analytic_plan_projects.id,
        })
        cls.analytic_account_partner_b = cls.env['account.analytic.account'].create({
            'name': 'analytic_account_partner_b',
            'partner_id': cls.partner_b.id,
            'plan_id': cls.analytic_plan_projects.id,
        })
        cls.analytic_account_administratif = cls.env['account.analytic.account'].create({
            'name': 'analytic_account_administratif',
            'plan_id': cls.analytic_plan_departments.id,
        })
        cls.analytic_account_administratif_2 = cls.env['account.analytic.account'].create({
            'name': 'analytic_account_administratif_2',
            'plan_id': cls.analytic_plan_departments.id,
        })

        # ==== Budget Analytic ====

        cls.budget_analytic_revenue = cls.env['budget.analytic'].create({
            'name': 'Budget 2019: Revenue',
            'date_from': '2019-01-01',
            'date_to': '2019-12-31',
            'budget_type': 'revenue',
            'state': 'draft',
            'user_id': cls.env.ref('base.user_admin').id,
            'budget_line_ids': [
                Command.create({
                    'budget_amount': 35000,
                    cls.project_column_name: cls.analytic_account_partner_a.id,
                }),
                Command.create({
                    'budget_amount': 10000,
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                }),
                Command.create({
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                    cls.department_column_name: cls.analytic_account_administratif.id,
                    'budget_amount': 10000.0,
                }),
            ]
        })

        cls.budget_analytic_expense = cls.env['budget.analytic'].create({
            'name': 'Budget 2019: Expense',
            'date_from': '2019-01-01',
            'date_to': '2019-12-31',
            'budget_type': 'expense',
            'state': 'draft',
            'user_id': cls.env.ref('base.user_admin').id,
            'budget_line_ids': [
                Command.create({
                    'budget_amount': 55000,
                    cls.project_column_name: cls.analytic_account_partner_a.id,
                }),
                Command.create({
                    'budget_amount': 9000,
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                }),
                Command.create({
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                    cls.department_column_name: cls.analytic_account_administratif.id,
                    'budget_amount': 10000.0,
                }),
            ]
        })

        cls.budget_analytic_both = cls.env['budget.analytic'].create({
            'name': 'Budget 2019: Both',
            'date_from': '2019-01-01',
            'date_to': '2019-12-31',
            'budget_type': 'both',
            'state': 'draft',
            'user_id': cls.env.ref('base.user_admin').id,
            'budget_line_ids': [
                Command.create({
                    'budget_amount': 20000,
                    cls.project_column_name: cls.analytic_account_partner_a.id,
                }),
                Command.create({
                    'budget_amount': 5000,
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                }),
                Command.create({
                    cls.project_column_name: cls.analytic_account_partner_b.id,
                    cls.department_column_name: cls.analytic_account_administratif.id,
                    'budget_amount': 10000.0,
                }),
            ]
        })

    def assertBudgetLine(self, budget_line, *, achieved):
        budget_line.invalidate_recordset(['achieved_amount'])
        self.assertRecordValues(budget_line, [{'achieved_amount': achieved}])
