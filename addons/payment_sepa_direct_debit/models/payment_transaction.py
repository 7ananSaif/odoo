# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    mandate_id = fields.Many2one(comodel_name='sdd.mandate', index=True)

    # === CRUD METHODS === #

    @api.model_create_multi
    def create(self, vals_list):
        txs = super().create(vals_list)
        sepa_txs = txs.filtered(
            lambda t: t.provider_code == 'custom'
            and t.provider_id.custom_mode == 'sepa_direct_debit'
            and t.token_id.sdd_mandate_id
        )
        for tx in sepa_txs:
            tx.mandate_id = tx.token_id.sdd_mandate_id
        return txs

    #=== BUSINESS METHODS ===#

    def _get_specific_processing_values(self, processing_values):
        """ Override of `payment` to return SEPA-specific processing values. """
        if self.provider_id.custom_mode != 'sepa_direct_debit' or self.operation == 'online_token':
            return super()._get_specific_processing_values(processing_values)

        return {
            'access_token': payment_utils.generate_access_token(self.reference),
        }

    def _send_payment_request(self):
        """Override of `payment` to create the related `account.payment` and notify the customer."""
        if self.provider_id.custom_mode != 'sepa_direct_debit':
            return super()._send_payment_request()

        mandate = self.token_id.sdd_mandate_id
        if not mandate:
            self._set_error(_("The token is not linked to a mandate."))
            return

        mandate._update_and_partition_state_by_validity()
        if mandate.state != 'active':
            self._set_error(_("The mandate is invalid."))
            return

        # There is no provider to send a payment request to, but we handle empty payment data
        # to let the payment engine call the generic processing methods.
        self._process('sepa_direct_debit', {'reference': self.reference})

    def _apply_updates(self, payment_data):
        """Override of `payment` to update the transaction based on the payment data."""
        if self.provider_id.custom_mode != 'sepa_direct_debit':
            return super()._apply_updates(payment_data)

        if self.operation in ('online_token', 'offline'):
            self._set_done()  # SEPA transactions are confirmed as soon as the mandate is valid.

    def _set_done(self, **kwargs):
        """ Override of `payment` to create the token and validate the mandate of confirmed SEPA
        transaction.

        Note: It would be preferred to do it in the post-processing, but the tokens must be created
        before Subscription checks for their existence during its own post-processing.
        """
        confirmed_txs = super()._set_done(**kwargs)
        sepa_txs = confirmed_txs.filtered(
            lambda t: t.provider_code == 'custom'
            and t.provider_id.custom_mode == 'sepa_direct_debit'
            and t.mandate_id
        )
        for tx in sepa_txs:
            existing_token = self.env['payment.token'].search(
                [('provider_id', '=', tx.provider_id.id), ('sdd_mandate_id', '=', tx.mandate_id.id)],
                limit=1,
            )
            tx.token_id = (
                existing_token
                or tx.provider_id._sdd_create_token_for_mandate(tx.partner_id, tx.mandate_id)
            )
            if tx.mandate_id.state == 'draft':
                tx.mandate_id._confirm()
        return confirmed_txs

    def _get_communication(self):
        """ Override of `payment_custom` to ensure the transaction reference is used as payment
        communication when requesting a SDD mandate.
        """
        if self.provider_id.custom_mode != 'sepa_direct_debit':
            return super()._get_communication()
        else:
            return self.reference

    def _create_payment(self, **extra_create_values):
        """ Override of `payment` to pass the correct payment method line id and the SDD mandate id
        to the extra create values.

        Note: self.ensure_one()

        :param dict extra_create_values: The optional extra create values.
        :return: The created payment.
        :rtype: recordset of `account.payment`
        """
        if self.provider_id.custom_mode != 'sepa_direct_debit':
            return super()._create_payment(**extra_create_values)

        if self.operation in ('online_token', 'offline'):
            mandate = self.token_id.sdd_mandate_id
        else:
            mandate = self.mandate_id

        payment_method_line = self.provider_id.journal_id.inbound_payment_method_line_ids.filtered(
            lambda l: l.payment_provider_id == self.provider_id
        )
        return super()._create_payment(
            payment_method_line_id=payment_method_line.id, sdd_mandate_id=mandate.id
        )
