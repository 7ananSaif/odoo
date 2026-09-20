from odoo import _, models, fields
from odoo.exceptions import UserError

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe, format_amount_to_stripe, make_request_stripe_proxy


class HrExpenseStripeTestPurchaseWizard(models.Model):
    _name = 'hr.expense.stripe.test.purchase.wizard'
    _description = 'Test Purchase Wizard for Stripe'

    company_id = fields.Many2one(comodel_name='res.company', required=True, default=lambda self: self.env.company.id)
    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', required=True)
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.stripe_currency_id.id,
    )
    card_currency_id = fields.Many2one(related='card_id.currency_id')
    amount_currency = fields.Monetary(string='Amount in currency', required=True, default=100.0, currency_field='currency_id')
    atm_fee = fields.Monetary(currency_field='currency_id')
    cashback_amount = fields.Monetary(currency_field='currency_id')
    authorization_method = fields.Selection(
        selection=[
            ('chip', "Chip"),
            ('contactless', "Contactless"),
            ('keyed_in', "Keyed in Manually"),
            ('online', "Online"),
            ('swipe', "swipe"),
        ],
        required=True,
        default='online',
    )
    merchant_name = fields.Char(required=True, default='Test Merchant')
    merchant_country_id = fields.Many2one(comodel_name='res.country', default=lambda self: self.env.company.country_id.id)
    mcc_id = fields.Many2one(
        comodel_name='product.mcc.stripe.tag',
        string='Merchant Category Code',
        required=True,
        default=lambda self: self.env['product.mcc.stripe.tag'].search([], limit=1),
    )
    capture = fields.Boolean(string="Capture if approved", default=True)
    force_capture = fields.Boolean(string="Simulate a Force Capture")
    capture_surcharge = fields.Monetary(currency_field='card_currency_id')
    split_capture = fields.Boolean(string="Capture in two transactions", default=False)

    def action_test_purchase(self):
        if self.env.company._get_stripe_mode() != 'test':
            raise UserError(_("Test purchase cannot be used on a live system"))

        base_route = 'test_helpers/authorizations'
        force_capture_route = 'test_helpers/transactions/create_force_capture'
        capture_route = f'{base_route}/{{authorization_id}}/capture'
        today = fields.Date.context_today(self)
        for wizard in self:
            stripe_id = wizard.company_id.sudo().stripe_id
            auth_id = False
            reason_auth_closed = 'unknown'
            if wizard.force_capture:
                amount_to_capture = wizard.currency_id._convert(
                    wizard.amount_currency,
                    wizard.card_currency_id,
                    wizard.company_id,
                    today,
                )
                is_auth_closed = False
            else:
                stripe_merchant_amount = format_amount_to_stripe(wizard.amount_currency, wizard.currency_id)
                payload = {
                    'account': stripe_id,
                    'card': wizard.card_id.stripe_id,
                    'authorization_method': wizard.authorization_method,
                    'currency': wizard.card_id.currency_id.name,
                    'merchant_data': {
                        'name': wizard.merchant_name,
                        'category': wizard.mcc_id.stripe_name,
                        'country': wizard.merchant_country_id.code,
                    },
                    'merchant_amount': stripe_merchant_amount,
                    'merchant_currency': wizard.currency_id.name,
                }
                if wizard.atm_fee:
                    payload.setdefault('amount_details', {})['atm_fee'] = format_amount_to_stripe(wizard.atm_fee, wizard.card_currency_id)
                if wizard.cashback_amount:
                    payload.setdefault('amount_details', {})['cashback_amount'] = format_amount_to_stripe(
                        wizard.cashback_amount,
                        wizard.card_currency_id,
                    )

                payload = {key: value for key, value in payload.items() if value is not False}
                response = make_request_stripe_proxy(wizard.company_id.sudo(), route=base_route, payload=payload, method='POST')

                auth_id = response['id']
                amount_to_capture = format_amount_from_stripe(response['amount'], wizard.card_currency_id)
                is_auth_closed = response['status']
                if response['request_history']:
                    reason_auth_closed = response['request_history'][0]['reason']

            if wizard.capture:
                if is_auth_closed == 'closed':
                    raise UserError(_(
                        "The test purchase was denied by Stripe with the following message: '%(reason)s'",
                        reason=reason_auth_closed,
                    ))

                total_to_capture = amount_to_capture + wizard.capture_surcharge
                total_captured_amount = format_amount_to_stripe(total_to_capture, wizard.card_currency_id)
                first_transaction_amount = total_captured_amount // (2 if wizard.split_capture else 1)

                closed_authorization = (
                    not wizard.split_capture
                    and not wizard.currency_id.compare_amounts(total_captured_amount, first_transaction_amount)
                )
                if wizard.force_capture:
                    payload = {
                        'account': stripe_id,
                        'amount': max(0, first_transaction_amount),
                        'currency': wizard.currency_id.name,
                        'card': wizard.card_id.stripe_id,
                    }
                else:
                    payload = {
                        'account': stripe_id,
                        'capture_amount': max(0, first_transaction_amount),
                        'close_authorization': closed_authorization,
                    }
                make_request_stripe_proxy(
                    wizard.company_id.sudo(),
                    route=force_capture_route if wizard.force_capture else capture_route,
                    route_params=None if wizard.force_capture else {'authorization_id': auth_id},
                    payload=payload,
                    method='POST',
                )
                if wizard.split_capture:
                    closed_authorization = True
                    if wizard.force_capture:
                        payload = {
                            'account': stripe_id,
                            'amount': max(0, total_captured_amount - first_transaction_amount),
                            'currency': wizard.currency_id.name,
                            'card': wizard.card_id.stripe_id,
                        }
                    else:
                        payload = {
                            'account': stripe_id,
                            'capture_amount': max(0, total_captured_amount - first_transaction_amount),
                            'close_authorization': closed_authorization,
                        }
                    make_request_stripe_proxy(
                        wizard.company_id.sudo(),
                        route=force_capture_route if wizard.force_capture else capture_route,
                        route_params=None if wizard.force_capture else {'authorization_id': auth_id},
                        payload=payload,
                        method='POST',
                    )
                if not closed_authorization and not wizard.force_capture:
                    payload = {
                        'account': stripe_id,
                        "status": "closed",
                    }
                    make_request_stripe_proxy(
                        wizard.company_id.sudo(),
                        route=f'{base_route}/{{authorization_id}}',
                        route_params={'authorization_id': auth_id},
                        payload=payload,
                        method='POST',
                    )
