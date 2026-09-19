from textwrap import dedent
from uuid import uuid4

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

ISO20022_CHARGE_BEARER_SELECTION = [
    ('CRED', "Creditor"),
    ('DEBT', "Debtor"),
    ('SHAR', "Shared"),
    ('SLEV', "Service Level"),
]
ISO20022_PRIORITY_SELECTION = [
    ('NORM', 'NORM - Normal'),
    ('HIGH', 'HIGH - High priority'),
    ('URGP', 'URGP - Critical urgency'),
    ('SVDA', 'SVDA - Same value date'),
]
ISO20022_PRIORITY_HELP = dedent('''\
    • NORM: Standard processing time.
    • HIGH: High priority payment.
    • URGP: Critical, requires immediate processing.
    • SVDA: Payments must settle on same day as submission.'''
)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    end_to_end_uuid = fields.Char(
        string='End to End ID',
        compute='_compute_end_to_end_uuid',
        store=True,
        index=True,
        help='Unique end-to-end assigned by the initiating party',
    )
    sepa_pain_version = fields.Selection(related='journal_id.sepa_pain_version')
    iso20022_uetr = fields.Char(
        string='UETR',
        compute='_compute_iso20022_uetr',
        store=True,
        help='Unique end-to-end transaction reference',
    )
    iso20022_priority = fields.Selection(
        string='Priority',
        selection=ISO20022_PRIORITY_SELECTION,
        compute='_compute_payment_method_priority',
        store=True, readonly=False,
        help=ISO20022_PRIORITY_HELP,
    )
    payment_method_is_iso20022 = fields.Boolean(related='payment_method_line_id.payment_method_id.is_iso20022')
    iso20022_charge_bearer = fields.Selection(
        string="Charge Bearer",
        selection=ISO20022_CHARGE_BEARER_SELECTION,
        compute='_compute_iso20022_charge_bearer',
        readonly=False,
        store=True,
        tracking=True,
        help="Specifies which party/parties will bear the charges associated with the processing of the payment transaction."
    )

    @api.depends('payment_method_id')
    def _compute_iso20022_charge_bearer(self):
        for payment in self:
            if payment.payment_method_id.code == 'sepa_ct':
                payment.iso20022_charge_bearer = 'SLEV'
            else:
                payment.iso20022_charge_bearer = payment.journal_id.iso20022_charge_bearer

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        res += ['sepa_ct', 'iso20022', 'iso20022_se', 'iso20022_ch', 'iso20022_us']
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super()._get_method_codes_needing_bank_account()
        res += ['sepa_ct', 'iso20022', 'iso20022_se', 'iso20022_ch', 'iso20022_us']
        return res

    @api.constrains('payment_method_line_id', 'journal_id')
    def _check_sepa_bank_account(self):
        sepa_payment_method = self.env.ref('account_iso20022.account_payment_method_sepa_ct')
        for rec in self:
            if rec.payment_method_id == sepa_payment_method:
                if not rec.journal_id.bank_account_id or not rec.journal_id.bank_account_id.acc_type == 'iban':
                    raise ValidationError(_("The journal '%s' requires a proper IBAN account to pay via SEPA. Please configure it first.", rec.journal_id.name))

    @api.constrains('payment_method_line_id', 'currency_id')
    def _check_sepa_currency(self):
        for rec in self:
            if rec.payment_method_id.code == 'sepa_ct' and rec.currency_id.name != 'EUR':
                raise ValidationError(_("SEPA only accepts payments in EUR."))

    def _get_payment_method_codes_to_exclude(self):
        res = super()._get_payment_method_codes_to_exclude()
        currency_codes = ['BGN', 'HRK', 'CZK', 'DKK', 'GIP', 'HUF', 'ISK', 'CHF', 'NOK', 'PLN', 'RON', 'SEK', 'GBP', 'EUR', 'XPF']
        currency_ids = self.env['res.currency'].with_context(active_test=False).search([('name', 'in', currency_codes)])
        sepa_ct = self.env.ref('account_iso20022.account_payment_method_sepa_ct', raise_if_not_found=False)
        if sepa_ct and self.currency_id not in currency_ids:
            res.append(sepa_ct.code)
        return res

    @api.depends('payment_method_id')
    def _compute_end_to_end_uuid(self):
        for payment in self:
            if not payment.end_to_end_uuid and payment.payment_method_id.code in {'iso20022', 'iso20022_se', 'iso20022_ch', 'iso20022_us', 'sepa_ct'}:
                payment.end_to_end_uuid = uuid4().hex

    @api.depends('payment_method_id')
    def _compute_iso20022_uetr(self):
        payments = self.filtered(
            lambda p: not p.iso20022_uetr and p.payment_method_id.code in ('iso20022', 'sepa_ct')
        )
        for payment in payments:
            payment.iso20022_uetr = uuid4()

    @api.depends('journal_id', 'payment_method_is_iso20022')
    def _compute_payment_method_priority(self):
        for payment in self:
            payment.iso20022_priority = (
                payment.payment_method_is_iso20022
                and payment.journal_id.iso20022_default_priority
            )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # If the import doesn't have an end_to_end_uuid, there's on need to compute one for it as it should only be
        # created by the initiating party.
        if self.env.context.get('import_file'):
            res.env.remove_to_compute(self._fields['end_to_end_uuid'], res)
        return res
