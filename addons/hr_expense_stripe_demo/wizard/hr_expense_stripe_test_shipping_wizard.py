from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.hr_expense_stripe.utils import make_request_stripe_proxy


class HrExpenseStripeCardShippingWizard(models.TransientModel):
    _name = 'hr.expense.stripe.test.shipping.wizard'
    _description = 'Wizard to manage the shipping of a physical card'

    company_id = fields.Many2one(comodel_name='res.company', required=True, default=lambda self: self.env.company.id)
    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', required=True)
    card_shipping_status = fields.Selection(related='card_id.shipping_status', readonly=True)

    new_shipping_status = fields.Selection(
        selection=[
            ('submit', "Submit for shipping"),
            ('ship', "Mark as shipped"),
            ('deliver', "Mark as delivered"),
            ('return', "Mark as returned"),
            ('fail', "Mark as delivery failed"),
        ],
        string="New Shipping Status",
        required=True,
        default='deliver',
    )

    def _test_shipping(self, new_status):
        self.ensure_one()
        if self.env.company._get_stripe_mode() != 'test':
            raise UserError(self.env._("Test shipping cannot be used on a live system"))

        if new_status not in ('submit', 'ship', 'deliver', 'return', 'fail'):
            raise UserError(self.env._("Invalid shipping status"))

        url = 'test_helpers/issuing/cards/{card_id}/shipping/{status}'

        make_request_stripe_proxy(
            self.company_id.sudo(),
            route=url,
            route_params={'card_id': self.card_id.stripe_id, 'status': new_status},
            payload={'account': self.company_id.sudo().stripe_id},
            method='POST',
        )

    def action_update_shipping_status(self):
        for wizard in self:
            if wizard.new_shipping_status == 'submit':
                wizard._test_shipping('submit')

            if wizard.new_shipping_status == 'ship':
                if wizard.card_shipping_status == 'pending':
                    wizard._test_shipping('submit')
                wizard._test_shipping('ship')

            if wizard.new_shipping_status in ('deliver', 'return', 'fail'):
                if wizard.card_shipping_status == 'pending':
                    wizard._test_shipping('submit')
                if wizard.card_shipping_status in ('pending', 'shipped'):
                    wizard._test_shipping('ship')
                wizard._test_shipping(wizard.new_shipping_status)

        return {'type': 'ir.actions.act_window_close'}
