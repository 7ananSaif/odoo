# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountFinancialYearOp(models.TransientModel):
    _inherit = 'account.financial.year.op'
    _description = 'Opening Balance of Financial Year'

    account_return_periodicity = fields.Selection(related='company_id.account_return_periodicity', string='Periodicity in month', readonly=False, required=True)
    account_tax_return_journal_id = fields.Many2one(related='company_id.account_tax_return_journal_id', string='Journal', readonly=False)
    account_return_reminder_day = fields.Integer(related='company_id.account_return_reminder_day', string='Reminder', readonly=False, required=True)
    vat_label = fields.Char(related="company_id.country_id.vat_label")

    def _company_fields_to_update(self):
        # Changing any of these fields can trigger generation of tax returns.  We are including them here so the
        # company is updated in a single write and return generation isn't run multiple times.
        return super()._company_fields_to_update() | {'account_return_periodicity', 'account_tax_return_journal_id', 'account_return_reminder_day'}

    def action_save_onboarding_fiscal_year(self):
        result_action = super().action_save_onboarding_fiscal_year()
        if self.env.context.get('open_account_return_on_save'):
            return self.env['account.return'].action_open_tax_return_view()
        return result_action
