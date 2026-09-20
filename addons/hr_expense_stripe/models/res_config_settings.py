from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stripe_id = fields.Char(related='company_id.stripe_id')
    stripe_account_issuing_status = fields.Selection(related="company_id.stripe_account_issuing_status", readonly=True)
    stripe_journal_id = fields.Many2one(
        comodel_name='account.journal',
        related='company_id.stripe_journal_id',
        readonly=False,
        check_company=True,
    )
    stripe_account_issuing_tos_accepted = fields.Boolean(related="company_id.stripe_account_issuing_tos_accepted", readonly=False)
    stripe_company_currency_id = fields.Many2one(related='company_id.stripe_currency_id')

    @api.model
    def open_expense_stripe_issuing_terms(self, params):
        return {
            'type': 'ir.actions.client',
            'tag': 'hr_expense_stripe.expense_stripe_issuing_terms',
        }

    def action_create_stripe_account(self):
        return self.company_id.action_create_stripe_account()

    def action_refresh_stripe_account(self):
        return self.company_id.action_refresh_stripe_account()

    def action_configure_stripe_account(self):
        return self.company_id.action_configure_stripe_account()
