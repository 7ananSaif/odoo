# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api, fields, models


_logger = logging.getLogger(__name__)

INT_PHONE_NUMBER_FORMAT_REGEX = r'^\+[^+]+$'


class SddMandate(models.Model):
    _inherit = 'sdd.mandate'

    is_online_payment = fields.Boolean(compute='_compute_is_online_payment')
    payment_transaction_ids = fields.One2many(
        string="Payment Transactions",
        comodel_name='payment.transaction',
        inverse_name='mandate_id',
    )
    payment_transaction_count = fields.Integer(
        string="No. of Payment Transactions",
        compute='_compute_payment_transaction_count',
    )

    def _compute_is_online_payment(self):
        # In sudo mode to read the custom_mode field of payment.provider.
        results = self.env['payment.transaction'].sudo()._read_group(
            domain=[
                ('mandate_id', 'in', self.ids),
                ('provider_id.custom_mode', '=', 'sepa_direct_debit'),
            ], groupby=['mandate_id'], aggregates=['__count'])
        data = {mandate.id: count > 0 for mandate, count in results}
        for mandate in self:
            mandate.is_online_payment = data.get(mandate.id, False)

    @api.depends('payment_transaction_ids')
    def _compute_payment_transaction_count(self):
        # In sudo mode to read the custom_mode field of payment.provider.
        results = self.env['payment.transaction'].sudo()._read_group(
            domain=[
                ('mandate_id', 'in', self.ids),
                ('provider_id.custom_mode', '=', 'sepa_direct_debit'),
            ], groupby=['mandate_id'], aggregates=['__count'])
        data = {mandate.id: count for mandate, count in results}
        for mandate in self:
            mandate.payment_transaction_count = data.get(mandate.id, 0)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') in ['closed', 'revoked']:
            linked_tokens = self.env['payment.token'].search([('sdd_mandate_id', 'in', self.ids)])
            linked_tokens.sudo().active = False  # In sudo mode to write on payment.token.
        return res

    def _confirm(self):
        """ Confirm the customer's ownership of the SEPA Direct Debit mandate. """
        template = self.env.ref('payment_sepa_direct_debit.mail_template_sepa_notify_validation')
        self.write({'state': 'active'})
        template.with_user(SUPERUSER_ID).send_mail(self.id)

    def action_validate_mandate(self):
        """ Override of `account_sepa_direct_debit` to create a token when validating mandates."""
        super().action_validate_mandate()
        sepa_provider_per_company = dict(self.env['payment.provider']._read_group([
            *self.env['payment.provider']._check_company_domain(self.company_id),
            ('custom_mode', '=', 'sepa_direct_debit'),
            ('is_published', '=', True),
            ('state', '!=', 'disabled'),
        ], groupby=['company_id'], aggregates=['id:recordset']))
        for mandate in self.filtered(lambda m: m.state == 'active'):
            provider = sepa_provider_per_company.get(mandate.company_id)
            if provider:
                provider[:1]._sdd_create_token_for_mandate(mandate.partner_id, mandate)

    def action_view_payment_transactions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Payments Transactions"),
            'res_model': 'payment.transaction',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_transaction_ids.ids)],
        }

    def _get_source_transaction(self):
        """Return the source transaction that initiated the creation of this SDD mandate."""
        self.ensure_one()
        return self.env['payment.transaction'].search([
            ('mandate_id', '=', self.id),
            ('state', '=', 'done'),
            ('provider_id.custom_mode', '=', 'sepa_direct_debit'),
        ], limit=1, order='id ASC')
