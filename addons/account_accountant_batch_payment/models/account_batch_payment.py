# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import Command, _, models


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    def action_open_batch_payment(self):
        self.ensure_one()
        return {
            'name': _("Batch Payment"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('account_batch_payment.view_batch_payment_form').id,
            'res_model': self._name,
            'res_id': self.id,
            'context': {
                'create': False,
                'delete': False,
            },
            'target': 'current',
        }

    def _get_amls_from_batch_payments(self, domain):
        amls = self.env['account.move.line']
        payment2amls = defaultdict(self.env['account.move.line'].browse)
        amls_to_create = []
        payments_with_move = self.payment_ids.filtered(lambda payment: payment.move_id)

        for payment in payments_with_move:
            liquidity_lines, _counterpart_lines, _writeoff_lines = payment._seek_for_lines()
            filtered_liquidity_lines = liquidity_lines.filtered_domain(domain)
            amls |= filtered_liquidity_lines
            payment2amls[payment] = filtered_liquidity_lines

        for payment, move_lines in payment2amls.items():
            amls_to_create += [
                move_line._get_aml_values(
                    balance=-move_line.balance,
                    amount_currency=-move_line.amount_currency,
                    reconciled_lines_ids=[Command.set(move_line.ids)],
                    payment_lines_ids=[Command.set(payment.ids)],
                ) for move_line in move_lines
            ]

        amls_to_create += (self.payment_ids - payments_with_move)._get_amls_for_payment_without_move()
        return amls, amls_to_create

    def _get_amls_for_reconciliation(self, st_line):
        amls_to_create, has_exchange_diff = self.payment_ids._get_amls_for_reconciliation(st_line)
        return amls_to_create, has_exchange_diff
