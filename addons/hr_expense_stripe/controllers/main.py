import base64
import logging

from odoo import SUPERUSER_ID, _, api
from odoo.exceptions import MissingError, ValidationError
from odoo.http import Controller, request, route
from odoo.tools.safe_eval import time

from odoo.addons.hr_expense_stripe.utils import STRIPE_REQUEST_REFUSED_REASONS, StripeIssuingDatabaseError, format_amount_from_stripe


_logger = logging.getLogger(__name__)


class StripeIssuingController(Controller):
    _webhook_url = 'stripe_issuing/webhook'

    @route(f"/{_webhook_url}/<string:company_uuid>", type='http', methods=['POST'], auth='public', csrf=False, save_session=False)
    def stripe_issuing_webhook(self, company_uuid):
        event = request.get_json_data()
        _logger.info(
            'Webhook "%(type)s" event (%(event_id)s) received to "%(url)s" from %(ip)s',
            {
                'type': event['type'],
                'event_id': event['id'],
                'url': f'{self._webhook_url}/{company_uuid}',
                'ip': request.httprequest.remote_addr,
            },
        )
        response_headers = {
            'Stripe-Version': event['api_version'],
            'Content-Type': 'application/json',
        }
        company_sudo = self.env['res.company'].sudo().search([('stripe_issuing_iap_webhook_uuid', '=', company_uuid)])
        if not company_sudo:
            response = {'message': 'Invalid webhook accessed'}
            return request.make_json_response(data=response, headers=response_headers, status=StripeIssuingDatabaseError.DB_WRONG_WEBHOOK)

        env = request.env(
            user=SUPERUSER_ID,
            su=True,
            context={'allowed_company_ids': company_sudo.ids},
        )
        signature_header = request.httprequest.headers.get('Iap-Signature')
        valid = self._validate_signature(company_sudo, signature_header, request.httprequest.data.decode())
        if not valid:
            response = {'message': 'Invalid or outdated signature found in the request'}
            return request.make_json_response(data=response, headers=response_headers, status=StripeIssuingDatabaseError.DB_WRONG_SIGNATURE)

        event_mode = 'live' if event['livemode'] else 'test'
        if company_sudo._get_stripe_mode() != event_mode:
            response = {'message': 'Event ignored as the event mode does not match the company mode'}
            return request.make_json_response(data=response, headers=response_headers)

        status = 200
        try:
            match event['type'].split('.'):
                case ('balance', 'available'):
                    response = self._process_balance_event(env, event)
                case ('issuing_authorization', _multiples):
                    response = self._process_authorization_event(env, event)
                case ('issuing_card', 'updated'):
                    response = self._process_card_event(env, event)
                case ('issuing_dispute', _multiples):
                    response = self._process_dispute_event(env, event)
                case ('issuing_transaction', _multiples):
                    response = self._process_transaction_event(env, event)
                case ('topup', 'succeeded'):
                    response = self._process_topup_event(env, event)
                case _:
                    response = {
                        'approved': False,
                        'message': f"Invalid event type '{event['type']}'",
                    }
        except Exception as e:  # noqa: BLE001 # Catch all exceptions to avoid crashing the webhook and having it disabled by Stripe
            response = {
                'approved': False,
                'message': str(e),
            }
            _logger.error(e)
            # Because the request awaits a response, we decline the authorization request to prevent the webhook from being disabled by Stripe
            status = StripeIssuingDatabaseError.DB_ERROR if event['type'] != 'issuing_authorization.request' else 200
        return request.make_json_response(data=response, headers=response_headers, status=status)

    # --------------------------------------------
    # Events processing methods
    # --------------------------------------------

    @api.model
    def _process_authorization_event(self, env, event):
        auth_object = event['data']['object']
        card = env['hr.expense.stripe.card'].search(
            [('stripe_id', '=', auth_object['card']['id']), ('company_id', '=', env.company.id)],
            limit=1,
        )
        if not card:
            raise MissingError(env._("A card that doesn't exist on the database was used"))
        if event['type'] == 'issuing_authorization.request':
            amount = format_amount_from_stripe(auth_object['pending_request']['amount'], card.currency_id)
            mcc = env['product.mcc.stripe.tag'].search([
                ('code', '=', auth_object['merchant_data']['category_code']),
            ])
            country = env['res.country'].search([('code', 'ilike', auth_object['merchant_data']['country'])], limit=1)

            can_pay, refusal_reason = card._can_pay_amount(amount, mcc, country)
            if can_pay:
                # We only create it when the capture happens
                return {'message': 'Authorization request approved', 'approved': True}
            else:
                # There will be no capture, we need to create a refused expense to log the refusal reason
                env['hr.expense']._create_from_stripe_authorization(auth_object, refusal_reason)
                return {'message': refusal_reason, 'approved': False}

        if event['type'] in {'issuing_authorization.created', 'issuing_authorization.updated'}:
            default_request_history = [{'approved': False, 'reason': _("Unknown")}]
            request_history = auth_object.setdefault('request_history', default_request_history)[0]
            if auth_object['status'] == 'closed' and not request_history['approved']:
                # There will be no capture, we need to create a refused expense to log the refusal reason
                technical_reason = request_history['reason']
                if technical_reason == 'webhook_declined':
                    refusal_reason = auth_object['metadata'].get('message', STRIPE_REQUEST_REFUSED_REASONS[request_history['reason']])
                else:
                    refusal_reason = STRIPE_REQUEST_REFUSED_REASONS[request_history['reason']]
                env['hr.expense']._create_from_stripe_authorization(auth_object, refusal_reason)
                return {'message': 'Refused expense created'}

            elif auth_object['status'] == 'pending':
                env['hr.expense']._create_from_stripe_authorization(auth_object)
                return {'message': 'Draft expense created'}

            return {'message': 'Event ignored, not a refused or draft expense'}
        raise ValidationError(env._("Invalid event type '%(invalid_event)s'", invalid_event=event['type']))

    @api.model
    def _process_balance_event(self, env, event):
        bal_object = event['data']['object']
        issuing_object = bal_object['issuing']
        company = env.company
        journal = company.stripe_journal_id
        last_balance_timestamp = journal.stripe_issuing_balance_timestamp
        if last_balance_timestamp > event['created']:
            return {'message': 'Balance ignored, a more recent one was already received'}
        stripe_currency = journal.stripe_currency_id
        if issuing_object['available']:  # May be empty if 0
            issuing_amount = format_amount_from_stripe(issuing_object['available'][0]['amount'], stripe_currency)
        else:
            issuing_amount = 0

        company.stripe_journal_id.write({
            'stripe_issuing_balance': issuing_amount,
            'stripe_issuing_balance_timestamp': event['created'],
        })

        return {'message': 'Balance updated'}

    @api.model
    def _process_card_event(self, env, event):
        card_object = event['data']['object']
        existing_card = env['hr.expense.stripe.card'].search(
            [('stripe_id', '=', card_object['id']), ('company_id', '=', env.company.id)],
            limit=1,
        )
        if not existing_card:
            raise ValidationError(env._("A card that doesn't exist on the database was used"))

        if (
            card_object['shipping'] and card_object['shipping'].get('status') in {'canceled', 'failure', 'returned'}
            and event['data']["previous_attributes"].get("shipping", {}).get("status")
        ):
            existing_card.with_context(skip_local_update=True)._create_or_update_card(state='canceled')
        else:
            existing_card._update_from_stripe(card_object)

        return {'message': 'Card updated'}

    @api.model
    def _process_transaction_event(self, env, event):
        tr_object = event['data']['object']
        authorization_id = tr_object['authorization']
        transaction_id = tr_object['id']

        split_id = False
        if transaction_id and not authorization_id:
            # In case of a force capture
            existing_expenses = env['hr.expense'].search([('stripe_transaction_id', '=', transaction_id)])

        elif authorization_id:
            existing_expenses = env['hr.expense'].search([('stripe_authorization_id', '=', authorization_id)])
            expense_transaction_ids = set(existing_expenses.mapped('stripe_transaction_id')) - {False}
            if expense_transaction_ids and transaction_id not in expense_transaction_ids:
                if len(existing_expenses) == 1:
                    split_id = (existing_expenses.split_expense_origin_id or existing_expenses).id
                else:
                    split_id = next(
                        s_id
                        for s_id
                        in (*existing_expenses.mapped('split_expense_origin_id').ids, min(existing_expenses.ids))
                        if s_id
                    )
                existing_expenses.split_expense_origin_id = split_id
                existing_expenses = env['hr.expense']  # If double transaction is detected, create a new existing_expenses
            elif expense_transaction_ids:
                existing_expenses = existing_expenses.filtered(lambda exp: exp.stripe_transaction_id == transaction_id)

        if tr_object['type'] == 'capture' and not existing_expenses:
            env['hr.expense']._create_from_stripe_transaction(tr_object, split_id=split_id)
        elif tr_object['type'] == 'capture' and existing_expenses:
            existing_expenses._update_from_stripe_transaction(tr_object)
        elif tr_object['type'] == 'refund' and existing_expenses:
            existing_expenses._stripe_cancel_expense_or_reverse_move(tr_object)
        if event['type'] == 'issuing_transaction.created':
            existing_statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', transaction_id)])
            if existing_statement_line:
                # if the event is sent twice
                existing_statement_line._update_from_stripe_transaction(tr_object)
            else:
                env['account.bank.statement.line']._create_from_stripe_transaction(tr_object)
        elif event['type'] == 'issuing_transaction.updated':
            statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', transaction_id)])
            statement_line._update_from_stripe_transaction(tr_object)
        return {'message': 'Expense & Bank Statement Line Created/Updated'}

    @api.model
    def _process_dispute_event(self, env, event):
        return {'message': 'Not Implemented'}

    @api.model
    def _process_topup_event(self, env, event):
        tu_object = event['data']['object']
        statement_line = env['account.bank.statement.line'].search([('stripe_id', '=', tu_object['id'])])
        if statement_line:
            return {'message': 'Top-up Bank Statement Line already exists, ignoring the event'}
        env['account.bank.statement.line']._create_from_stripe_topup(tu_object)
        return {'message': 'Top-up Bank Statement Line Create/updated'}

    # --------------------------------------------
    # Helpers
    # --------------------------------------------
    @api.model
    def _validate_signature(self, company, signature_header, payload_str):
        if not signature_header or not company:
            return False

        signature_data_dict = {}
        for key_value_str in signature_header.split(','):
            key, value = key_value_str.split('=', 1)
            if key in signature_data_dict:
                # If the key already exists, it means the signature is malformed
                return False
            signature_data_dict[key] = value

        if 'v1' not in signature_data_dict or 't' not in signature_data_dict:
            return False

        signature = base64.b64decode(signature_data_dict['v1'] + '==')  # Ensure padding is correct for base64 decoding
        timestamp = signature_data_dict['t']
        time_since_signed = time.time() - int(timestamp)
        signature_validity = 60 * 5  # 5 min
        if time_since_signed > signature_validity:
            return False
        signed_message = f'{timestamp}.{payload_str}'.encode()
        public_key = company.sudo().stripe_issuing_iap_public_key_id
        return public_key._verify(signed_message, signature)
