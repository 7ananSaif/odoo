from odoo import _, api, models


class HrExpenseStripeCard(models.Model):
    _inherit = 'hr.expense.stripe.card'

    @api.depends('last_4')
    def _compute_card_number(self):
        for card in self:
            last4 = card.last_4 if card.last_4 else '****'
            card.card_number_public = f"**** **** **** {last4}"

    def action_create_test_purchase(self):
        self.ensure_one()

        wizard = self.env['hr.expense.stripe.test.purchase.wizard'].create({
            'company_id': self.company_id.id,
            'card_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Simulate Card Purchase"),
            'view_mode': 'form',
            'res_model': wizard._name,
            'target': 'new',
            'context': self.env.context,
            'views': [[False, 'form']],
            'res_id': wizard.id
        }

    def action_open_shipping_wizard(self):
        self.ensure_one()
        wizard = self.env['hr.expense.stripe.test.shipping.wizard'].create({
            'company_id': self.company_id.id,
            'card_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Manage Card Shipping"),
            'view_mode': 'form',
            'res_model': wizard._name,
            'target': 'new',
            'context': self.env.context,
            'views': [[False, 'form']],
            'res_id': wizard.id
        }

    def _update_from_stripe(self, stripe_object):
        # Stripe doesn't provide tracking info in test mode, so we fake it here.
        if stripe_object.get('shipping') and stripe_object['shipping']['status'] == 'shipped' and self.env.company._get_stripe_mode() == 'test':
            stripe_object['shipping']['tracking_url'] = stripe_object['shipping']['tracking_url'] or 'https://www.dhl.com/tracking-info?trackingNumber=faketrackingnumber'
            stripe_object['shipping']['tracking_number'] = stripe_object['shipping']['tracking_number'] or 'faketrackingnumber'

        super()._update_from_stripe(stripe_object)
