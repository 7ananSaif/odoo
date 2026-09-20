#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrSalaryRule(models.Model):
    _name = 'hr.salary.rule'
    _inherit = ['hr.salary.rule', "analytic.mixin"]

    account_debit = fields.Many2one(
        'account.account', 'Debit Account', company_dependent=True, ondelete='restrict',
        help="Default account defined on the journal of the salary structure."
    )
    account_credit = fields.Many2one(
        'account.account', 'Credit Account', company_dependent=True, ondelete='restrict')
    not_computed_in_net = fields.Boolean(
        string="Excluded from Net", default=False,
        help='If checked, the result of this rule will not be taken into account in the Net salary rule in the journal entries. A specific debit/credit account should be set to consider it independently.')
    debit_tag_ids = fields.Many2many(
        string="Debit Tax Grids",
        comodel_name='account.account.tag',
        relation='hr_salary_rule_debit_tag_rel',
        help="Tags assigned to this line will impact financial reports when translated into an accounting journal entry."
            "They will be applied on the debit account line in the journal entry.",
    )
    credit_tag_ids = fields.Many2many(
        string="Credit Tax Grids",
        comodel_name='account.account.tag',
        relation='hr_salary_rule_credit_tag_rel',
        help="Tags assigned to this line will impact financial reports when translated into an accounting journal entry."
            "They will be applied on the credit account line in the journal entry.",
    )
    split_move_lines = fields.Boolean(
        string="Split on names",
        help="Enable this option to split the accountig entries for this rule according to the payslip line name. It could be useful for deduction/reimbursement or salary adjustments for instance.")
    employee_move_line = fields.Boolean(
        string="Set employee on account line",
        help="Enable this option to set the employee on the journal items of the payslips.")
    batch_payroll_move_lines = fields.Boolean(
        compute='_compute_batch_payroll_move_lines')
    analytic_distribution = fields.Json(groups="hr.group_hr_user")

    @api.depends_context('company')
    def _compute_batch_payroll_move_lines(self):
        self.batch_payroll_move_lines = self.env.company.batch_payroll_move_lines
