from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.hr_expense_stripe.utils import make_request_stripe_proxy, format_amount_to_stripe


class HrExpenseStripeTopupWizard(models.TransientModel):
    _name = 'hr.expense.stripe.topup.wizard'
    _description = "Stripe Issuing Top-up Wizard"
    _check_company_auto = True

    pull_push_funds = fields.Selection(selection=[
            ('push', 'Push Funds to a Funding Instruction'),
            ('pull', 'Directly pull funds from the company bank account'),
        ],
        compute='_compute_pull_push_funds',
    )
    company_id = fields.Many2one(comodel_name='res.company', string="Company", readonly=True, required=True)
    currency_id = fields.Many2one(comodel_name='res.currency', string="Currency", readonly=True, required=True)
    partner_bank_id = fields.Many2one(comodel_name='res.partner.bank', string="IBAN", readonly=True)
    account_number = fields.Char(string="Account number", related='partner_bank_id.acc_number', readonly=True)
    bic = fields.Char(string="BIC", related='partner_bank_id.bank_bic', readonly=True)
    qr_code = fields.Html(string="QR Code URL", compute="_compute_qr_code")
    is_live_mode = fields.Boolean(string="Live Mode", readonly=True, required=True, default=True)
    amount = fields.Monetary(string="Amount", currency_field='currency_id', default=1000.0)
    statement_description = fields.Char(
        string="Bank statement description",
        default=lambda self: self.env._("Stripe Top-Up"),
        size=15,
    )

    @api.constrains('statement_description')
    def _check_statement_is_only_ascii(self):
        for wizard in self:
            if not wizard.statement_description:
                continue
            try:
                wizard.statement_description.encode('ascii')
            except UnicodeEncodeError:
                raise ValidationError(_("The statement description can only contain 15 ASCII characters"))

    @api.depends('company_id')
    def _compute_pull_push_funds(self):
        for wizard in self:
            wizard.pull_push_funds = 'pull' if wizard.company_id.country_code == 'US' else 'push'

    @api.model
    def _create_from_funding_instructions(self, fi_object):
        """ Set up the displayed data according to the `funding_instruction` object sent by Stripe
            This also creates a partner and banking information for Stripe so it can be reused
        """
        currency = self.env['res.currency'].search([('name', 'ilike', fi_object['currency'])], limit=1)
        if not currency:
            raise UserError(_(
                "Currency %(name)s is not available in the system. Please activate it",
                name=fi_object['currency'],
            ))

        financial_address = None
        supported_networks = []

        for address in fi_object['bank_transfer']['financial_addresses']:
            financial_address = address[address['type']]
            supported_networks = address['supported_networks']
            break

        if not financial_address:
            raise UserError(_("Only IBAN is supported for Stripe Issuing funding instructions right now"))

        if not 'sepa' in supported_networks:
            raise UserError(_("Only SEPA is supported for Stripe Issuing funding instructions right now"))

        # Search or create the partner
        partner_bank = self.env['res.partner.bank'].search(
            domain=[('acc_number', '=', financial_address['iban'])],
            limit=1,
        )

        if not partner_bank:
            partner_country = self.env['res.country'].search([('code', 'ilike', financial_address['country'])], limit=1)
            account_holder_address = financial_address['account_holder_address']
            state = self.env['res.country.state'].search([('name', 'ilike', account_holder_address['state'])], limit=1)
            partner = self.env['res.partner'].create([{
                'name': financial_address['account_holder_name'],
                'country_id': partner_country and partner_country.id,
                'state_id': state and state.id,
                'is_company': True,
                'city': account_holder_address['city'],
                'street': account_holder_address['line1'],
                'street2': account_holder_address['line2'],
                'zip': account_holder_address['postal_code'],
                'website': 'https://www.stripe.com',
            }])

            bank = self.env['res.bank'].search([('bic', 'ilike', financial_address['bic'])], limit=1)
            if not bank:
                bank_address = financial_address['bank_address']
                bank_country = self.env['res.country'].search([('code', 'ilike', bank_address['country'])], limit=1)
                bank_state = self.env['res.country.state'].search([('name', 'ilike', bank_address['state'])], limit=1)
                bank = self.env['res.bank'].create([{
                    'name': _("Stripe Partner Bank"),
                    'bic': financial_address['bic'],
                    'country': bank_country and bank_country.id,
                    'state': bank_state and bank_state.id,
                    'city': bank_address['city'],
                    'street': bank_address['line1'],
                    'street2': bank_address['line2'],
                    'zip': bank_address['postal_code'],
                }])

            partner_bank = self.env['res.partner.bank'].create([{
                'acc_number': financial_address['iban'],
                'currency_id': currency.id,
                'partner_id': partner.id,
                'bank_id': bank.id,
                'allow_out_payment': True,
            }])

        return self.create([{
            'company_id': self.env.company.id,
            'currency_id': currency.id,
            'is_live_mode': fi_object['livemode'],
            'pull_push_funds': 'push',
            'partner_bank_id': partner_bank.id,
        }])

    @api.depends('partner_bank_id', 'amount', 'currency_id')
    def _compute_qr_code(self):
        for wizard in self:
            bank = wizard.partner_bank_id
            if (
                    wizard.pull_push_funds == 'pull'
                    or not (bank and bank.allow_out_payment and wizard.amount and wizard.currency_id)
            ):
                wizard.qr_code = False
                continue

            b64_qr = bank.build_qr_code_base64(
                amount=wizard.amount,
                free_communication=_("Top up payment"),
                structured_communication=False,
                currency=wizard.currency_id,
                debtor_partner=bank.partner_id,
            )
            if b64_qr:
                wizard.qr_code = (
                    f'<img class="border border-dark rounded" src="{b64_qr}"/>'
                    f'<br/><strong>{_("Scan me with your banking app.")}</strong>'
                )
            else:
                wizard.qr_code = False

    def action_topup(self):
        """ US only, send the topup request to stripe so we can test payments without going to stripe dashboard  """
        self.ensure_one()
        if self.pull_push_funds == 'push' or self.company_id.country_code != 'US':
            raise UserError(_("The direct top-up isn't available outside of the US."))

        payload = {
            'account': self.sudo().company_id.stripe_id,
            'amount': format_amount_to_stripe(self.amount, self.currency_id),
            'currency': self.currency_id.name,
            'statement_descriptor': self.statement_description,
        }

        response = make_request_stripe_proxy(self.company_id.sudo(), route='topups', payload=payload, method='POST')
        match response['status']:
            case 'pending' | 'succeeded':
                self.env.user._bus_send('simple_notification', {
                    'type': 'success',
                    'message': _("Top-up request successfully sent to Stripe, this can take a few days before being available"),
                })
            case 'failed':
                msg = response.get('description', _("Unknown"))
                self.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'message': _("Top-up request failed with the following error sent by Stripe:\n%(stripe_error)s", stripe_error=msg),
                })  # What if it fails? What if we want to cancel it (US-case TBDL) ?
