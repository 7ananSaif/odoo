import datetime
import logging
from collections import defaultdict

from odoo import _, _lt, api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

from odoo.addons.hr_expense_stripe.utils import STRIPE_CURRENCY_MINOR_UNITS, make_request_stripe_proxy

_logger = logging.getLogger(__name__)

# So it can be translated in the database, and sent to Transifex. And manually updated in IAP
_lt("The code to access your Odoo Expense Card is: %(code)s")
_lt(
    "The phone number associated with your Odoo Expense card(s) has been updated. "
    "If it was not requested by you, please contact your administrator."
)


# Maybe better to have the direct URLs that Stripe gives us, but in test mode we don't have any tracking URL
CARRIER_URLS = {
    'dhl': r'https://www.dhl.com/',
    'fedex': r'https://www.fedex.com/',
    'royal_mail': r'https://www.royalmail.com/',
    'usps': r'https://tools.usps.com/',
}


# https://docs.stripe.com/api/issuing/cards
class HrExpenseStripeCard(models.Model):
    _name = 'hr.expense.stripe.card'
    _inherit = ['mail.thread']
    _description = "Employee Expense Card"
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of
    _mail_post_access = 'read'

    name = fields.Char(string="Name", compute="_compute_name", store=True, required=True)
    stripe_id = fields.Char(string="Stripe Card ID", readonly=True, copy=False, index='btree')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    company_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Company Partner",
        related='company_id.partner_id',
        readonly=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string="Cardholder",
        check_company=True,
        domain=[('user_id', '!=', False)],
        required=True,
        tracking=True,
    )
    has_employee = fields.Boolean(compute='_compute_from_employee', compute_sudo=True)
    employee_name = fields.Char(compute='_compute_from_employee', compute_sudo=True)
    user_id = fields.Many2one(related='employee_id.user_id', related_sudo=True)
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Stripe Journal",
        default=lambda self: self.env.company.stripe_journal_id,
        domain=[('type', '=', 'bank'), ('bank_statements_source', '=', 'stripe_issuing')],
        check_company=True,
        required=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(related='company_id.stripe_currency_id')
    delivery_address_id = fields.Many2one(
        comodel_name='res.partner',
        string="Delivery Address",
        help="The address where the card will be delivered.",
        tracking=True,
        domain="""[
            '|', ('employee', '=', True),
            '|', ('id', '=', company_partner_id),
            '&', ('parent_id.employee', '=', 'True'), ('type', '=', 'delivery'),
        ]""",
    )

    state = fields.Selection(  # Stripe states
        string="Status",
        selection=[
            ('draft', "Draft"),
            ('pending', "Pending"),
            ('inactive', "Inactive"),
            ('active', "Active"),
            ('canceled', "Blocked"),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
    )
    card_type = fields.Selection(  # Stripe types
        string="Type",
        selection=[
            ('physical', "Physical"),
            ('virtual', "Virtual"),
        ],
        default='virtual',
        required=True,
    )

    # Post Creation Card Data
    last_4 = fields.Char(string="Last 4 digits", copy=False, readonly=True, size=4)
    card_name = fields.Char(string="Card Name", help="The name displayed on the card", copy=False, readonly=True)
    expiration = fields.Char(string="Expiration Date", size=5, copy=False, readonly=True)
    card_number_public = fields.Char(string="Card Number", compute='_compute_card_number')

    # Post Creation Physical Card Data
    shipping_status = fields.Selection(
        string="Shipping Status",
        selection=[
            ('canceled', "Canceled"),
            ('delivered', "Delivered"),
            ('failure', "Failure"),
            ('pending', "Pending"),
            ('returned', "Returned"),
            ('shipped', "Shipped"),
            ('submitted', "Submitted"),
        ],
        readonly=True,
        copy=False,
        tracking=True,
    )
    tracking_url = fields.Char(string="Tracking URL", copy=False, readonly=True)
    tracking_number = fields.Char(string="Tracking Number", copy=False, readonly=True)
    shipping_estimated_delivery = fields.Datetime(string="Estimated Delivery", copy=False, readonly=True)
    ordered_by = fields.Many2one(comodel_name='res.users', string="Ordered By", copy=False, readonly=True)
    is_delivered = fields.Boolean(string="Terms and Conditions acceptance", default=False, copy=False, readonly=True, tracking=True)

    # Block card flow
    cancellation_reason = fields.Selection(
        string="Cancellation Reason",
        selection=[
            ('design_rejected', "Design Rejected"),  # Because it exists on stripe
            ('lost', "Lost"),
            ('stolen', "Stolen"),
            ('none', "Other"),  # 'none' is a Stripe value, but we use it to mean "other" in Odoo
        ],
        readonly=True,
        tracking=True,
    )

    # Spending Policy
    spending_policy_category_tag_ids = fields.Many2many(
        comodel_name='product.mcc.stripe.tag',
        string="Merchant Category Codes",
        help="Whitelist of merchant codes, to define which type of goods or services would be authorized.",
        domain=[('product_id', '!=', False)],
        tracking=True,
    )

    spending_policy_country_tag_ids = fields.Many2many(
        comodel_name='res.country',
        string="Countries",
        help="Whitelist of countries where payments could be authorized from.",
        default=lambda self: self.env.company.country_id.ids,
        tracking=True,
    )

    spending_policy_transaction_amount = fields.Monetary(
        string="Transaction Limit",
        currency_field='currency_id',
        tracking=True,
    )
    spending_policy_interval_amount = fields.Monetary(
        string="Card Limit",
        currency_field='currency_id',
        tracking=True,
    )
    spending_policy_interval = fields.Selection(
        string="Limit Frequency",
        selection=[
           ('daily', "Day"),
           ('weekly', "Week"),
           ('monthly', "Month"),
           ('yearly', "Year"),
           ('all_time', "All Time"),
        ],
        default='all_time',
        required=True,
        tracking=True,
    )

    expense_ids = fields.One2many(comodel_name='hr.expense', inverse_name='card_id', string='Expenses')
    expenses_count = fields.Integer(compute='_compute_expenses_count', compute_sudo=True)
    payment_method_line_id = fields.Many2one(
        comodel_name='account.payment.method.line',
        string='Payment Method Line',
        readonly=True,
        index=True,
    )
    has_limit_higher_than_stripe_warning = fields.Boolean(
        string="Warning",
        compute='_compute_has_limit_higher_than_stripe_warning',
        compute_sudo=True,
        help="Warning if the limit is higher than the Stripe limit",
        readonly=True,
    )

    @api.ondelete(at_uninstall=False)
    def _prevent_unlink_cards(self):
        """ Cards should never be deleted, unless the module is removed """
        for card in self:
            if card.stripe_id and not self.env.su:
                raise ValidationError(_("You can't delete a card that already exists for Stripe, please block it instead"))

    @api.constrains('company_id')
    def _check_company_id(self):
        for card in self:
            if not card.company_id.stripe_id:
                raise ValidationError(self.env._("The Stripe issuing account isn't properly set. Please connect to Stripe in the settings"))

    @api.constrains('employee_id')
    def _check_employee_has_user(self):
        for card in self:
            if not card.employee_id.user_id:
                raise ValidationError(self.env._("The employee must have a user to be able to access safely their card."))

    @api.constrains('ordered_by')
    def _check_ordered_by(self):
        for card in self:
            if card.card_type == 'physical' and not card.ordered_by and card.state != 'draft':
                raise ValidationError(self.env._("The card must be ordered by a user."))

    @api.constrains('is_delivered')
    def _check_is_delivered(self):
        for card in self:
            if card.card_type == 'physical' and not card.is_delivered and card.state not in {'draft', 'pending'}:
                raise ValidationError(self.env._("The card must have a delivery date if it is marked as delivered."))

    @api.constrains('delivery_address_id')
    def _check_delivery_address_id(self):
        if self.card_type == 'physical' and self.state != 'draft':
            delivery_address = self.delivery_address_id
            if not delivery_address:
                raise ValidationError(self.env._("The delivery address must be set before activating the card."))

            if not all([delivery_address.street, delivery_address.city, delivery_address.zip, delivery_address.country_id]):
                raise ValidationError(self.env._("The delivery address must have a street, city, zip code and country set."))

            if 'EU' not in (delivery_address.country_id.country_group_codes or []):
                raise ValidationError(self.env._("The delivery address must be in the European Union."))

    @api.depends('last_4')
    def _compute_card_number(self):
        for card in self:
            last4 = card.last_4 if card.last_4 and card.state != 'pending' else '****'
            card.card_number_public = f"**** **** **** {last4}"

    @api.depends('employee_id')
    def _compute_name(self):
        for card in self:
            if card.employee_id and not card.name:
                card.name = card.employee_id.name

    @api.depends('employee_id')
    def _compute_from_employee(self):
        for card in self:
            card.has_employee = bool(card.employee_id)
            # Safe to bypass security for the name as the field is also on hr.employee.public
            card.employee_name = card.employee_id.name

    @api.depends('expense_ids')
    def _compute_expenses_count(self):
        for card in self:
            card.expenses_count = len(card.expense_ids)

    @api.depends('spending_policy_interval_amount', 'spending_policy_transaction_amount', 'spending_policy_interval')
    def _compute_has_limit_higher_than_stripe_warning(self):
        # Never change this value unless changing it also on IAP,
        # it bumps the default value set by Stripe. Currency-agnostic, but it's ok for now
        stripe_limit = 50000 * STRIPE_CURRENCY_MINOR_UNITS.get(self.currency_id.name, 2)
        interval_multiplier_map = {'daily': 1, 'weekly': 7, 'monthly': 30, 'yearly': 365, 'all_time': 1}  # All time will be ignored
        for card in self:
            interval = card.spending_policy_interval
            interval_amount = card.spending_policy_interval_amount if interval != 'all_time' else 0
            card.has_limit_higher_than_stripe_warning = (
                interval_amount > stripe_limit * interval_multiplier_map[interval]
                or card.spending_policy_transaction_amount > stripe_limit
            )

    def _track_subtype(self, init_values):
        self.ensure_one()
        if self.is_delivered and init_values.get('state') == 'pending':
            card_received_subtype = self.env.ref('hr_expense_stripe.mt_stripe_card_received', raise_if_not_found=False)
            return card_received_subtype or super()._track_subtype(init_values)
        return super()._track_subtype(init_values)

    def _create_or_update_card(self, state='inactive', cancellation_reason=None):
        self.ensure_one()
        payload = {'account': self.company_id.sudo().stripe_id, 'status': state}
        if cancellation_reason:
            payload['cancellation_reason'] = cancellation_reason
        if self.stripe_id:
            route = 'cards/{card_id}'
            route_params = {'card_id': self.stripe_id}
        else:
            route = 'cards'
            route_params = {}
            currency_name = self.currency_id and self.currency_id.name
            payload.update({
                'type': self.card_type,
                'currency': currency_name or False,
                'cardholder': self.employee_id.private_stripe_id,
            })
        if (
            self.card_type == 'physical'
            and self.shipping_status in {False, 'pending'}
            and self.state in {'draft', 'pending'}
            and state in {'draft', 'inactive'}
        ):
            payload.update({
                "shipping[name]": self.delivery_address_id.name or self.employee_id.name,
                "shipping[address][line1]": self.delivery_address_id.street,
                "shipping[address][line2]": self.delivery_address_id.street2,
                "shipping[address][city]": self.delivery_address_id.city,
                "shipping[address][state]": self.delivery_address_id.state_id.name,
                "shipping[address][postal_code]": self.delivery_address_id.zip,
                "shipping[address][country]": self.delivery_address_id.country_id.code,
            })
        payload = {key: value for key, value in payload.items() if value is not False}  # Else Stripe consider it a value
        response = make_request_stripe_proxy(self.company_id.sudo(), route, route_params, payload, method='POST')

        if not self.env.context.get('skip_local_update'):
            self._update_from_stripe(response)
        if not self.payment_method_line_id:
            payment_method = self.env['account.payment.method'].search([('code', '=', 'stripe_issuing')], limit=1)
            if not payment_method:
                payment_method = self.env['account.payment.method'].sudo().create([{
                    'name': 'Stripe Issuing Card',
                    'code': 'stripe_issuing',
                    'payment_type': 'outbound',
                }]).sudo(self.env.su)
            self.payment_method_line_id = self.env['account.payment.method.line'].sudo().create([{
                 'name': _("Stripe Card ending with %(last_4)s", last_4=self.last_4),
                'journal_id': self.journal_id.id,
                'payment_method_id': payment_method.id,
            }])

    def _update_from_stripe(self, stripe_object):
        """
        Updates a card from a Stripe card object See: https://docs.stripe.com/api/issuing/cards/object
        """
        self.ensure_one()
        if self.stripe_id and self.stripe_id != stripe_object['id']:
            raise UserError(_("Failed to update card from Stripe. You are trying to update the wrong card."))
        new_vals = {}
        emails_to_send = []
        if not self.stripe_id:
            new_vals['stripe_id'] = stripe_object['id']
        if self.state != stripe_object['status']:
            # When a physical card is ordered and hasn't been delivered we want to set the state to pending.
            if not self.is_delivered and self.card_type == 'physical' and self.state == 'draft' and stripe_object['status'] == 'inactive':
                new_vals['state'] = 'pending'
                emails_to_send.append('ordered')
            # If the card is virtual or if the card is updated to another state than from inactive, we want to exit the pending state.
            # It's possible through the stripe dashboard but shouldn't happen through Odoo.
            elif self.card_type == 'virtual' or self.state != 'pending' or stripe_object['status'] != 'inactive':
                new_vals['state'] = stripe_object['status']
                if self.state == 'draft':
                    # Only possible for virtual cards as physical cards are set to pending when draft
                    emails_to_send.append('assigned')
        if not self.cancellation_reason:
            new_vals['cancellation_reason'] = stripe_object['cancellation_reason']
        if not self.last_4:
            new_vals['last_4'] = stripe_object['last4']
        if not self.expiration:
            exp_month = stripe_object['exp_month']
            exp_year = stripe_object['exp_year'] % 100
            new_vals['expiration'] = f'{exp_month:02}/{exp_year:02}'
        if self.card_type == 'physical':
            if stripe_object['shipping']['status'] != self.shipping_status:
                # Since it's not possible to go back in shipping status, we only update it if it's a progression.
                # In case the webhooks are received out of order.
                states = {False: 0, 'submitted': 1, 'pending': 2, 'shipped': 3, 'delivered': 4, 'failure': 4, 'returned': 4, 'canceled': 4}
                if states[stripe_object['shipping']['status']] > states[self.shipping_status]:
                    new_vals['shipping_status'] = stripe_object['shipping']['status']
                    if new_vals['shipping_status'] in {'canceled', 'failure', 'returned'}:
                        emails_to_send.append('canceled')
                    elif new_vals['shipping_status'] == 'shipped':
                        emails_to_send.append('shipped')
            if not self.tracking_url:
                new_vals['tracking_url'] = stripe_object['shipping']['tracking_url']
            if not self.tracking_number:
                new_vals['tracking_number'] = stripe_object['shipping']['tracking_number']
            shipping_eta = datetime.datetime.fromtimestamp(stripe_object['shipping']['eta'])
            if stripe_object['shipping']['eta'] and shipping_eta != self.shipping_estimated_delivery:
                new_vals['shipping_estimated_delivery'] = shipping_eta

        self.write(new_vals)
        for email_type in emails_to_send:
            self._send_delivery_emails(email_type=email_type)

    def _send_delivery_emails(self, email_type='ordered'):
        """
        Send the mails to the cardholder('s manager) of a physical card to notify them of the card status
        :param str email_type: ordered | shipped, type of the mail to send
        """
        self.ensure_one()
        if email_type not in {'canceled', 'ordered', 'assigned', 'shipped'}:
            raise UserError(self.env._("Invalid email type, must be 'canceled', 'ordered', 'assigned' or 'shipped'."))
        template_ref = f'hr_expense_stripe.email_template_hr_expense_stripe_card_{email_type}'

        template_context = {
            'shipping_estimated_delivery': format_date(
                self.env,
                self.shipping_estimated_delivery,
                self.env.user.tz or self.ordered_by.tz,
            ),
        }
        delivery_address = self.delivery_address_id
        if (
            email_type in {'canceled', 'shipped'}
            and delivery_address
            and (delivery_address.is_company or delivery_address.parent_id.is_company or delivery_address.company_name)
        ):
            # If we're delivering to a company building
            email_to = self.ordered_by.email_formatted
            email_cc = None
            template_context['recipient_name'] = self.ordered_by.name
        elif email_type == 'assigned':
            email_to = self.employee_id.work_email
            email_cc = None
            template_context['recipient_name'] = self.employee_id.name
        else:
            email_to = self.employee_id.work_email
            email_cc = self.ordered_by.email_formatted
            template_context['recipient_name'] = self.employee_id.name

        template = self.env.ref(template_ref, raise_if_not_found=False)
        if template and email_to:
            can_sudo = self.employee_id in self.env.user.employee_ids or self.env.su
            template.sudo(can_sudo).with_context(**template_context).send_mail(self.id, email_values={'email_to': email_to, 'email_cc': email_cc})

    def _can_pay_amount(self, amount, mcc, country):
        """ Check if the card employee is still valid, and apply spending policy rules

        :param float amount: The amount of the payment to check
        :param :class:`~hr_expense_stripe.models.product_mcc_stripe_tag.ProductMCCSTripeTag` mcc: The MCC of the merchant
        :param :class:`~odoo.addons.base.models.res_country.ResCountry` country: The country of the merchant
        :return: (can_pay, refusal_reason)
        :rtype: tuple[bool, str]
        """
        def process_existing_expenses_data(data_raw):
            """ Process the existing expenses data to get the amount spent in the different intervals and MCCs """
            today = fields.Date.context_today(self)
            limit_interval_start_date = {
                'daily': today,
                'weekly': fields.Date.start_of(today, 'week'),
                'monthly': fields.Date.start_of(today, 'month'),
                'yearly': fields.Date.start_of(today, 'year'),
            }
            data = {
                'daily': defaultdict(int),
                'weekly': defaultdict(int),
                'monthly': defaultdict(int),
                'yearly': defaultdict(int),
                'all_time': defaultdict(int),
            }
            for date, mcc_id, datum_amount in data_raw:
                data['all_time'][mcc_id] += datum_amount
                for interval in ('daily', 'weekly', 'monthly', 'yearly'):
                    if today >= limit_interval_start_date[interval]:
                        data[interval][mcc_id] += datum_amount
            return data

        def get_already_spent(interval, mccs_to_check, existing_expenses_data):
            """ Return the summed amount already spent in the given aggregated in the given interval MCCs """
            return sum(
                amount
                for existing_mcc, amount in existing_expenses_data[interval].items()
                if not mccs_to_check or existing_mcc in mccs_to_check
            )

        card = self.ensure_one().with_company(self.company_id)
        # Validate employee
        if not card.employee_id.active:
            return False, _("Invalid Employee")

        # Validate transaction maximum
        if (
                not card.currency_id.is_zero(card.spending_policy_transaction_amount)
                and card.currency_id.compare_amounts(amount, card.spending_policy_transaction_amount) > 0
        ):
            return False, _("Transaction amount exceeds the maximum allowed")

        # Validate Country
        card_country_ids = set(card.spending_policy_country_tag_ids.ids)
        if not country:
            return False, _("No country found")
        if country.id not in card_country_ids and card_country_ids:
            return False, _("Country not allowed")

        # Validate MCC
        if not mcc:
            return False, _("No MCC found")

        valid_mcc = card.env['product.mcc.stripe.tag'].search([('product_id', '!=', False)])
        if not valid_mcc:
            return False, self.env._("No MCC is properly set")

        card_mccs = card.spending_policy_category_tag_ids or valid_mcc  # If no MCC is set, we allow all valid MCCs
        if mcc not in card_mccs:
            return False, _("MCC not allowed")

        # Validate Limits
        existing_expenses_data = process_existing_expenses_data(card.env['hr.expense']._read_group(
            domain=[('card_id', '=', card.id), ('state', '!=', 'refused')],
            groupby=['date:day', 'mcc_tag_id'],
            aggregates=['total_amount:sum'],
        ))

        if not card.currency_id.is_zero(card.spending_policy_interval_amount):
            mccs = card_mccs
            amount_already_spent = get_already_spent(card.spending_policy_interval, mccs, existing_expenses_data)
            if card.currency_id.compare_amounts(amount_already_spent + amount, card.spending_policy_interval_amount) > 0:
                return False, _("Transaction amount exceeds the interval limit")

        return True, _("Transaction accepted")

    def action_open_expenses(self):
        return self.expense_ids._get_records_action(
            name=_("Expense") if len(self.expense_ids) == 1 else _("Expenses"),
            context={'create': False},
        )

    def action_activate_card(self):
        """ Activates the ability to pay with the card on Stripe and on the record """
        self.ensure_one()

        if (
            not self.env.user.has_group('hr_expense.group_hr_expense_manager')
            and (self.state != 'pending' or self.sudo().employee_id.user_id == self.env.user)  # The employee can activate their own card when they receive it
        ):
            raise UserError(_("Operation only allowed for expense administrators."))

        if not self.stripe_id and not self.employee_id.private_stripe_id:
            return self.with_context({'stripe_card_action_activate': True}).action_open_cardholder_wizard()

        state = 'active'
        if self.card_type == 'physical' and self.state == 'draft':
            delivery_address = self.delivery_address_id
            if not delivery_address:
                raise ValidationError(self.env._("The delivery address must be set before activating the card."))

            if not all([delivery_address.street, delivery_address.city, delivery_address.zip, delivery_address.country_id]):
                raise ValidationError(self.env._("The delivery address must have a street, city, zip code and country set."))

            if 'EU' not in (delivery_address.country_id.country_group_codes or []):
                raise ValidationError(self.env._("The delivery address must be in the European Union."))

            state = 'inactive'
            self.ordered_by = self.env.user

        if self.state == 'pending':
            response = make_request_stripe_proxy(
                self.company_id.sudo(),
                'cardholders/{cardholder_id}',
                route_params={'cardholder_id': self.employee_id.sudo().private_stripe_id},
                payload={'account': self.company_id.sudo().stripe_id},
                method='GET',
            )
            ctx = {'default_card_id': self.id}
            phone_number = response.get('phone_number')
            if phone_number:
                ctx['default_phone_number'] = phone_number
                ctx['default_original_phone_number'] = phone_number
            billing_country_code = response.get('billing', {}).get('address', {}).get('country')
            if billing_country_code:
                ctx['default_billing_country_code'] = billing_country_code
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._("Card Activation"),
                'view_mode': 'form',
                'res_model': 'hr.expense.stripe.card.receive.wizard',
                'target': 'new',
                'context': ctx,
            }

        return self._create_or_update_card(state=state)

    def action_block_card(self):
        """ Hard block the card on Stripe and on the record, this is not reversible !!"""
        self.ensure_one()

        return self.env['hr.expense.stripe.card.block.wizard'].create([{'card_id': self.id}])._get_records_action(
            target='new',
            name=_("Block a Card"),
        )

    def action_pause_card(self):
        """ Sets the card state on "inactive on Stripe and on the record, disallowing the ability to use it unless reactivated """
        for card in self.filtered(lambda c: c.state == 'active'):
            is_own_card = card.employee_id.user_id == self.env.user
            card.sudo(is_own_card or self.env.su)._create_or_update_card(state='inactive')

    def action_open_cardholder_wizard(self):
        """ Open the Wizard to create/update the cardholder on stripe for the related employee"""
        self.ensure_one()
        employee_id = self.env.context.get('selected_employee_id', self.employee_id.id)
        if not employee_id:
            raise UserError(_("No valid employee selected, please set an employee to be able to update its cardholder data"))
        wizard = self.env['hr.expense.stripe.cardholder.wizard']._create_from_card(
            company=self.company_id,
            employee=self.env['hr.employee'].browse(employee_id),
            card=self,
        )
        return wizard._get_records_action(name=_("Cardholder Configuration"), target='new')

    def action_pause_card_warning_view(self):
        """ Warns the user to prevent it from pausing the card unexpectedly while messing around and find out they can't activate it again
        """
        self.ensure_one()

        if self.employee_id.user_id != self.env.user and not self.env.user.has_group('hr_expense.group_hr_expense_manager'):
            raise UserError(self.env._("Request only allowed for the cardholder or the managers."))

        return {
            'type': 'ir.actions.client',
            'tag': 'hr_expense_stripe.pause_card_warning_action',
            'target': 'new',
            'params': {
                'res_id': self.id,
            },
            'context': {
                'dialog_size': 'medium',
            }
        }

    def action_open_card_private_view(self):
        """ Open the view containing the Stripe IFrames showing the sensitive data"""
        self.ensure_one()

        if self.employee_id.user_id != self.env.user:
            raise UserError(self.env._("Request only allowed for the cardholder."))

        return {
            'type': 'ir.actions.client',
            'tag': 'hr_expense_stripe.private_card_view_action',
            'target': 'new',
            'params': {
                'res_id': self.id,
                'stripe_id': self.stripe_id,
            },
            'context': {
                'dialog_size': 'medium',
            }
        }

    def action_send_iap_2fa_code(self):
        """ Request SMS 2FA when creating the card """
        self.ensure_one()

        if self.employee_id.user_id != self.env.user:
            raise UserError(self.env._("Request only allowed for the cardholder."))

        # The text is translated in the database, so it can be sent to Transifex and translated there, but it is manually updated in IAP
        # to ensure no "Attack by translation" is possible.
        payload = {
            'account': self.company_id.sudo().stripe_id,
            'card_id': self.stripe_id,
            'lang': self.env.lang,
        }
        return make_request_stripe_proxy(self.company_id.sudo(), 'send_verification_code', payload=payload, method='POST')

    def action_request_ephemeral_key(self, nonce, one_time_code, session):
        """ Request the client key for the direct connection to Stripe, in order to retrieve the sensitive information """
        if self.employee_id.user_id != self.env.user:
            raise UserError(_("Request only allowed for the cardholder."))

        self.ensure_one()
        payload = {
            'cardholder_id': self.employee_id.sudo().private_stripe_id,
            'account': self.company_id.sudo().stripe_id,
            'issuing_card': self.stripe_id,
            'lang': self.env.lang,
            'session': session,
            'nonce': nonce,
            'verification_code': one_time_code,
        }
        return make_request_stripe_proxy(self.company_id.sudo(), 'ephemeral_keys', payload=payload, method='POST')

    def action_open_employee(self):
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.public',
        }
        if len(self) == 1:
            action.update({
                'name': _("Cardholder"),
                'view_mode': 'form',
                'res_id': self.sudo().employee_id.id,
            })
        else:
            action.update({
                'name': _("Cardholders"),
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.sudo().employee_id.ids)],
            })
        if self.employee_id.has_access('read'):
            action['res_model'] = 'hr.employee'
        return action

    def get_stripe_js_init_params(self):
        if self.employee_id.user_id != self.env.user:
            raise UserError(_("Request only allowed for the cardholder."))

        account_id = self.company_id.sudo().stripe_id
        if not account_id:
            raise UserError(_("You must create a Stripe account in order to use Stripe"))

        public_key = self.env['ir.config_parameter'].sudo().get_param(f'hr_expense_stripe.{self.company_id.id}_stripe_issuing_pk', '')

        if not public_key:
            raise UserError(_("The Stripe public key is missing"))

        return {
            'account': account_id,
            'public_key': public_key
        }

    def write(self, vals):
        if self.filtered(lambda card: card.state != 'draft'):
            if vals.get('state') == 'draft':
                raise UserError(self.env._("You can't set the card state back to draft."))
            if 'card_type' in vals:
                raise UserError(self.env._("You can't change the card type once the card has been created."))
            if 'delivery_address_id' in vals and self.shipping_status != 'pending':
                raise UserError(self.env._("You can't change the delivery address once the card has been shipped."))
        res = super().write(vals)
        if any(self.filtered(lambda card: card.state != 'draft' or card.stripe_id)) and vals.get('employee_id'):
            raise UserError(self.env._("You can't change the employee of an active card. Please create a new card instead."))
        if 'delivery_address_id' in vals and self.shipping_status == 'pending':
            self._create_or_update_card(self.state if self.state != 'pending' else 'inactive')
        return res
