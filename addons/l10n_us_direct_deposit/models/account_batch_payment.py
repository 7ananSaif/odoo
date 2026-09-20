# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
from uuid import uuid4

from odoo import fields, models, modules
from odoo.exceptions import UserError

from .wise_request import Wise


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    wise_batch_identifier = fields.Char(string='Wise Batch ID', readonly=True, copy=False)
    wise_payments_enabled = fields.Boolean(compute='_compute_wise_payments_enabled')
    wise_payment_status = fields.Selection(
        string='Wise Status',
        selection=[
            ('uninitiated', 'Uninitiated'),
            ('new', 'New'),
            ('completed', 'Completed'),
        ],
        default='uninitiated', readonly=True, copy=False,
    )

    def _compute_wise_payments_enabled(self):
        for batch in self:
            batch.wise_payments_enabled = batch.company_id.wise_connected and batch.payment_method_code == 'wise_direct_deposit'

    def open_wise_batch(self):
        self.ensure_one()
        if not self.wise_batch_identifier or not self.wise_payments_enabled:
            raise UserError(self.env._("This batch payment is not yet created in Wise."))

        url = "https://sandbox.transferwise.tech" if self.company_id.wise_environment == 'sandbox' else "https://wise.com"
        return {
            'type': 'ir.actions.act_url',
            'url': f"{url}/transactions/activities/by-resource/BATCH_TRANSFER/{self.wise_batch_identifier}",
        }

    def check_payments_for_warnings(self):
        rslt = super().check_payments_for_warnings()

        if not self.wise_payments_enabled:
            return rslt

        if len(self.payment_ids):
            if payments_in_future := self.payment_ids.filtered(lambda payment: payment.date != fields.Date.context_today(self)):
                rslt.append({
                    'title': self.env._("Wise will send the entire batch payment as soon as you fund it."),
                    'records': payments_in_future,
                    'help': self.env._("Scheduled payments are not yet supported."),
                })
        return rslt

    def check_payments_for_errors(self):
        rslt = super().check_payments_for_errors()

        if not self.wise_payments_enabled:
            return rslt

        if len(self.payment_ids):
            if non_usd_payments := self.payment_ids.filtered(lambda payment: payment.currency_id.name != 'USD'):
                rslt.append({
                    'title': self.env._("All payments in the batch must be in USD."),
                    'records': non_usd_payments,
                    'help': self.env._("Non-USD payments are not yet supported."),
                })
        return rslt

    def _send_after_validation(self):
        if self.payment_method_code != 'wise_direct_deposit' or not self.wise_payments_enabled:
            return super()._send_after_validation()

        wise_api = Wise(self.company_id)

        if not self.wise_batch_identifier:
            batch_group = wise_api.create_batch_group(currency=self.currency_id.name, batch_name=self.name)
            if wise_api.has_errors(batch_group):
                raise UserError(self.env._("Failed to create a batch on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(batch_group)))

            self.wise_batch_identifier = batch_group['id']
            self.wise_payment_status = 'new'
            if self._can_commit():
                self.env.cr.commit()

        if self.payment_ids.partner_bank_id.filtered(lambda bank: not bank.wise_bank_account):
            all_recipients = wise_api.get_recipients()
            if wise_api.has_errors(all_recipients):
                raise UserError(self.env._("Failed to load vendors from Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(all_recipients)))
            recipients_dict = {self._generate_wise_key(recipient=recipient): recipient for recipient in all_recipients['content']}

        for payment in self.payment_ids:
            # Find or create a recipient for the partner
            if not payment.partner_bank_id.wise_bank_account:
                matched_recipient = recipients_dict.get(self._generate_wise_key(payment=payment))
                if not matched_recipient:
                    matched_recipient = wise_api.create_recipient(self._prepare_wise_recipient_data(payment))
                    if wise_api.has_errors(matched_recipient):
                        raise UserError(self.env._("Failed to create a vendor on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(matched_recipient)))

                payment.partner_bank_id.wise_bank_account = matched_recipient['id']
                if self._can_commit():
                    self.env.cr.commit()

            # Create one transfer that links quote and batch together
            if not payment.wise_transfer_identifier:
                # Create one quote per payment
                quote = wise_api.create_quote({
                    "sourceCurrency": payment.currency_id.name,
                    "targetCurrency": payment.currency_id.name,
                    "targetAmount": payment.amount,
                    "targetAccount": payment.partner_bank_id.wise_bank_account,
                    "payOut": "BALANCE",
                })
                if wise_api.has_errors(quote):
                    raise UserError(self.env._("Failed to create a quote on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(quote)))

                transfer = wise_api.create_transfer_in_batch(self.wise_batch_identifier, self._prepare_wise_transfer_data(payment, quote['id']))
                if wise_api.has_errors(transfer):
                    raise UserError(self.env._("Failed to create a transfer on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(transfer)))

                payment.wise_transfer_identifier = transfer['id']
                if self._can_commit():
                    self.env.cr.commit()

        # Mark the batch as complete for the one click pay on redirect.
        batch_information = wise_api.get_batch_group(self.wise_batch_identifier)
        if wise_api.has_errors(batch_information):
            raise UserError(self.env._("Failed to retrieve batch information on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(batch_information)))

        status = wise_api.complete_batch_group(self.wise_batch_identifier, batch_information.get('version'))
        if wise_api.has_errors(status):
            raise UserError(self.env._("Failed to mark the batch as complete on Wise:\n%(wise_error)s", wise_error=wise_api.format_errors(status)))

        self.wise_payment_status = status['status'].lower()
        url = "https://sandbox.transferwise.tech" if self.company_id.sudo().wise_environment == 'sandbox' else "https://wise.com"
        super()._send_after_validation()

        return {
            'type': 'ir.actions.act_url',
            'url': f"{url}/transactions/batch/{self.wise_batch_identifier}",
        }

    @staticmethod
    def _can_commit():
        """ Helper to know if we can commit the current transaction or not.

        :returns: True if commit is acceptable, False otherwise.
        """
        return not modules.module.current_test

    def _generate_wise_key(self, payment=None, recipient=None):
        """Build a dictionary key to see that the partner matches the recipient
        by checking for the same account informations (routing/account number
        or account type) as well as personal information (name/email)."""
        if not payment and not recipient:
            return None

        if payment:
            partner = payment.partner_id
            bank_account = payment.partner_bank_id
            key_elements = [partner.name, partner.email]
            if bank_account.bank_id.country_code and bank_account.bank_id.country_code != 'US':  # Always use SWIFT outside of the US
                key_elements.extend(['swift_code', bank_account.bank_bic])
            else:
                key_elements.extend([bank_account.wise_account_type, bank_account.l10n_us_bank_account_type, bank_account.clearing_number])

        if recipient:
            key_elements = [recipient['name']['fullName'], recipient['email']]
            if recipient['type'].lower() == 'swift_code':
                key_elements.extend(['swift_code', recipient['details']['swiftCode']])
            else:
                key_elements.extend([recipient['type'].lower(), recipient['details']['accountType'].lower(), recipient['details']['abartn']])
        return tuple(key_elements)

    def _prepare_wise_recipient_data(self, payment):
        """Prepare data to create a Wise recipient from a partner and payment"""
        partner = payment.partner_id
        bank_account = payment.partner_bank_id
        if not bank_account:
            raise UserError(self.env._("The journal '%s' must have a linked bank account to create a Wise recipient.", payment.journal_id.name))

        bank_data = {
            "profile": self.company_id.sudo().wise_profile_identifier,
            "accountHolderName": partner.name,
            "currency": payment.currency_id.name,
            "details": {
                "address": {
                    "city": partner.city,
                    "country": partner.country_id.code,
                    "postCode": partner.zip,
                    "state": partner.state_id.code,
                    "firstLine": partner.street,
                },
                "legalType": "PRIVATE" if partner.company_type == 'person' else "BUSINESS",
                "accountNumber": bank_account.acc_number,
                "email": partner.email,
            },
        }

        if bank_account.bank_id.country_code and bank_account.bank_id.country_code != 'US':  # Always use SWIFT outside of the US
            bank_data["type"] = "swift_code"  # always use SWIFT outside of the US.
            bank_data['details']['swiftCode'] = bank_account.bank_bic
        else:
            bank_data["type"] = bank_account.wise_account_type
            bank_data['details']['accountType'] = bank_account.l10n_us_bank_account_type
            bank_data['details']['abartn'] = bank_account.clearing_number
        return bank_data

    def _prepare_wise_transfer_data(self, payment, quote_id):
        bank_account = payment.partner_bank_id
        if not payment.wise_unique_reference:
            payment.wise_unique_reference = uuid4()

        reference = payment.memo or payment.name
        reference = re.sub(r'[^\w\s]', '', reference)
        return {
            'targetAccount': bank_account.wise_bank_account,
            'quoteUuid': quote_id,
            'customerTransactionId': payment.wise_unique_reference,
            'details': {'reference': reference[:10]},
        }
