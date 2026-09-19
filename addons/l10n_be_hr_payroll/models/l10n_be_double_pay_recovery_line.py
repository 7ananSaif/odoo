# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

# This model is a persistant copy of l10n.be.double.pay.recovery.line.wizard
# it will be used as default values for the wizard.


class L10nBeDoublePayRecoveryLine(models.Model):
    _name = 'l10n.be.double.pay.recovery.line'
    _description = 'CP200: Double Pay Recovery Line Wizard'

    employee_id = fields.Many2one('hr.employee', ondelete='cascade', index='btree_not_null')
    amount = fields.Monetary(string="Amount", required=True, help="Holiday pay amount on the holiday attest from the previous employer")
    occupation_rate = fields.Float(required=True, help="Included between 0 and 100%")
    company_id = fields.Many2one('res.company', related='employee_id.company_id')
    currency_id = fields.Many2one(related='company_id.currency_id')
    months_count = fields.Float(string="# Months")
    company_calendar = fields.Many2one(related='company_id.resource_calendar_id')
    year = fields.Integer()

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=False)

    @api.depends('months_count', 'amount', 'occupation_rate', 'currency_id.symbol')
    def _compute_display_name(self):
        for record in self:
            currency = record.currency_id.symbol
            record.display_name = self.env._('%(months)s months: %(amount).2f%(currency)s (%(rate).0f%%)',
                months=record.months_count,
                amount=record.amount,
                currency=currency,
                rate=record.occupation_rate,
            )
