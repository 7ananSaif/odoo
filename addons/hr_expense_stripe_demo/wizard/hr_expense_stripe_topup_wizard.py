from odoo import _, models
from odoo.addons.hr_expense_stripe.utils import make_request_stripe_proxy, format_amount_to_stripe
from odoo.exceptions import UserError


class HrExpenseStripeTopupWizard(models.TransientModel):
    _inherit = 'hr.expense.stripe.topup.wizard'

    def action_simulate_topup(self):
        """ Test-mode push only, send the topup simulation request to stripe so we can test payments without going to stripe dashboard  """
        self.ensure_one()

        if self.is_live_mode or self.pull_push_funds == 'pull':
            raise UserError(_("The indirect top-up simulation isn't available in your country."))

        payload = {
            'account': self.sudo().company_id.stripe_id,
            'amount': format_amount_to_stripe(self.amount, self.currency_id),
            'currency': self.currency_id.name,
        }

        make_request_stripe_proxy(self.company_id.sudo(), 'test_helpers/fund_balance', payload=payload, method='POST')
