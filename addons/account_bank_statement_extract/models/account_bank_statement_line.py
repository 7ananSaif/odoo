from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    debit = fields.Monetary(compute='_compute_debit_credit', inverse='_inverse_debit')
    credit = fields.Monetary(compute='_compute_debit_credit', inverse='_inverse_credit')

    @api.depends('amount')
    def _compute_debit_credit(self):
        for line in self:
            line.debit = -line.amount if line.amount < 0.0 else 0.0
            line.credit = line.amount if line.amount > 0.0 else 0.0

    @api.onchange('debit')
    def _inverse_debit(self):
        for line in self:
            if line.debit:
                line.credit = 0
            if line.debit != line._origin.debit:
                line.amount = line.credit - line.debit

    @api.onchange('credit')
    def _inverse_credit(self):
        for line in self:
            if line.credit:
                line.debit = 0
            if line.credit != line._origin.credit:
                line.amount = line.credit - line.debit
