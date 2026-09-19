# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models

class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'

    @api.depends('res_model', 'res_id')
    def _compute_warning_message(self):
        subscription_wizard = self.env['payment.link.wizard']
        for wizard in self:
            if wizard.res_model != 'sale.order':
                continue
            order = self.env['sale.order'].browse(wizard.res_id)
            if not order.plan_id and (order.has_recurring_line and not order._subscription_is_one_time_sale()):
                wizard.warning_message = self.env._('You cannot generate a payment link for a recurring product without a recurring plan.')
                subscription_wizard |= wizard
                continue
            if order.plan_id and not order.has_recurring_line:
                wizard.warning_message = self.env._('You cannot generate a payment link for a recurring plan without a recurring product.')
                subscription_wizard |= wizard
                continue
            if order.subscription_state == '5_renewed':
                wizard.warning_message = _("You cannot generate a payment link for a renewed subscription")
                subscription_wizard |= wizard
        super(PaymentLinkWizard, self - subscription_wizard)._compute_warning_message()
