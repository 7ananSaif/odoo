import ast
from collections import defaultdict

from odoo import Command, models
from odoo.tools.float_utils import float_compare


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_open_manual_reconciliation_widget(self):
        ''' Open the manual reconciliation widget for the current payment.
        :return: A dictionary representing an action.
        '''
        self.ensure_one()
        action_values = self.env['ir.actions.act_window']._for_xml_id('account_accountant.action_move_line_posted_unreconciled')
        if self.partner_id:
            context = ast.literal_eval(action_values['context'])
            context.update({'search_default_partner_id': self.partner_id.id})
            if self.partner_type == 'customer':
                context.update({'search_default_trade_receivable': 1})
            elif self.partner_type == 'supplier':
                context.update({'search_default_trade_payable': 1})
            action_values['context'] = context
        return action_values

    def button_open_statement_lines(self):
        # OVERRIDE
        """ Redirect the user to the statement line(s) reconciled to this payment.
            :return: An action to open the view of the payment in the reconciliation widget.
        """
        self.ensure_one()

        default_statement_line = self.reconciled_statement_line_ids[-1]
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            extra_domain=[('id', 'in', self.reconciled_statement_line_ids.ids)],
            default_context={
                'create': False,
                'default_st_line_id': default_statement_line.id,
                'default_journal_id': default_statement_line.journal_id.id,
            },
            name=self.env._("Matched Transactions")
        )

    def _get_amls_for_payment_without_move(self):
        valid_payment_states = ['draft', *self.env['account.batch.payment']._valid_payment_states()]
        lines_to_create = []
        for payment in self:
            if payment.state not in valid_payment_states:
                continue

            line2amount = defaultdict(float)

            payment_term_lines = payment.invoice_ids.line_ids.filtered(lambda line: line.display_type == "payment_term" and not line.reconciled).sorted("date")
            remaining = payment.amount_signed
            for line in payment_term_lines:
                if not remaining:
                    break

                if float_compare(payment.amount_signed, 0, payment.currency_id.decimal_places) >= 0:
                    current = min(remaining, line.currency_id._convert(from_amount=line.amount_currency, to_currency=payment.currency_id))
                else:
                    current = max(remaining, line.currency_id._convert(from_amount=line.amount_currency, to_currency=payment.currency_id))
                remaining -= current
                line2amount[line] -= current

            if remaining:
                line2amount[False] -= remaining

            for line, amount in line2amount.items():
                if line:
                    line_to_create = line._get_aml_values(
                        name=payment.name,
                        balance=payment.currency_id._convert(from_amount=amount, to_currency=self.env.company.currency_id),
                        amount_currency=amount,
                        reconciled_lines_ids=[Command.set(line.ids)],
                        payment_lines_ids=[Command.set(payment.ids)],
                    )
                else:
                    partner_account = (
                        payment.partner_id.property_account_payable_id
                        if payment.payment_type == "outbound"
                        else payment.partner_id.property_account_receivable_id
                    )
                    line_to_create = {
                        'name': payment.name,
                        'partner_id': payment.partner_id.id,
                        'account_id': partner_account.id,
                        'currency_id': payment.currency_id.id,
                        'amount_currency': amount,
                        'balance': payment.currency_id._convert(from_amount=amount, to_currency=self.env.company.currency_id),
                        'payment_lines_ids': [Command.set(payment.ids)],
                    }
                lines_to_create.append(line_to_create)
        return lines_to_create

    def _get_aml_amount_in_payment_currency(self, aml):
        """ Converts the account move line's amount into its payment's (self) currency.

            :param aml: the account move line from which the amount has to be converted
            :return: the converted account move line amount, in the payment (self) currency
        """
        self.ensure_one()
        comp_curr = aml.company_id.currency_id
        if self.currency_id == aml.currency_id:
            amount = aml.amount_residual_currency
        elif self.currency_id == comp_curr:
            # Foreign currency on aml but the company currency one on the payment.
            amount = aml.currency_id._convert(from_amount=aml.amount_residual_currency, to_currency=self.currency_id, date=self.date)
        else:
            # Currency on payment different from that of the company or aml
            amount = comp_curr._convert(from_amount=aml.amount_residual, to_currency=self.currency_id, date=self.date)
        return amount

    def _get_amls_for_reconciliation(self, st_line):
        """ Fetch all amls linked to self, in a context of a bank statement line reconciliation.
            Taken in chronological order, returns the account move lines paid by self, in the limit
            of the payment amount. If the payment amount is larger than the sum of the amls amount,
            an additional residual line will fill the rest.

            :param st_line: the statement line for which we need the amls from self
            :return: amls_to_create, a list of lines (as dicts) to add to the reconciliation, fetched from self
                     has_exchange_diff, boolean indicating if an exchange difference was computed for at least one aml
        """
        def get_current_amount(payment, line_amount, remaining):
            return min(remaining, line_amount) if payment.currency_id.compare_amounts(payment.amount_signed, 0) >= 0 else max(remaining, line_amount)

        amls_to_create = []
        has_exchange_diff = False
        payments_with_move = self.filtered(lambda payment: payment.move_id)
        _transaction_amount, transaction_currency, _journal_amount, _journal_currency, _company_amount, company_currency = st_line._get_accounting_amounts_and_currencies()
        domain = st_line._get_default_amls_matching_domain()

        for payment in payments_with_move:
            liquidity_lines, _counterpart_lines, _writeoff_lines = payment._seek_for_lines()
            filtered_liquidity_lines = liquidity_lines.filtered_domain(domain)
            for payment_move_line in filtered_liquidity_lines:
                exchange_diff_balance = st_line._lines_get_account_balance_exchange_diff(payment_move_line.currency_id, payment_move_line.amount_residual, payment_move_line.amount_residual_currency)
                has_exchange_diff = has_exchange_diff or not payment_move_line.currency_id.is_zero(exchange_diff_balance)
                amls_to_create.append(
                    payment_move_line._get_aml_values(
                        balance=-(payment_move_line.amount_residual + exchange_diff_balance),
                        amount_currency=-payment_move_line.amount_currency,
                        reconciled_lines_ids=[Command.set(payment_move_line.ids)],
                        payment_lines_ids=[Command.set(payment.ids)],
                    ),
                )

        valid_payment_states = ['draft', *self._valid_payment_states()]
        for payment in (self - payments_with_move):
            if payment.state not in valid_payment_states:
                continue

            payment_term_lines = payment.invoice_ids.line_ids.filtered(lambda line: line.display_type == "payment_term" and not line.reconciled).sorted("date")
            remaining = payment.amount_signed
            for line in payment_term_lines:
                if payment.currency_id.is_zero(remaining):
                    break

                line_amount = payment._get_aml_amount_in_payment_currency(line)
                current_amount = get_current_amount(payment, line_amount, remaining)
                exchange_diff_balance = st_line._lines_get_account_balance_exchange_diff(line.currency_id, line.amount_residual, line.amount_residual_currency)
                amls_to_add = [line._get_aml_values(
                    name=line.name,
                    balance=line.currency_id._convert(from_amount=-current_amount, to_currency=company_currency, date=st_line.date),
                    amount_currency=-current_amount,
                    reconciled_lines_ids=[Command.set(line.ids)],
                    payment_lines_ids=[Command.set(payment.ids)],
                )]

                if line.currency_id == payment.currency_id:     # Payments in another currency than the invoice's currently don't handle EPDs
                    lines_with_epd, _total_amount, total_amount_currency = st_line._apply_early_payment_discount(
                        line,
                        current_amount - line_amount,
                        transaction_currency,
                        exchange_diff_balance,
                    )
                    amls_to_add = lines_with_epd or amls_to_add
                    current_amount = total_amount_currency or current_amount
                    if len(lines_with_epd) == 1:
                        # If the EPD needed a payment with move, we should handle the current payment (without move) already linked to the line invoice.
                        # It should not be possible to have multiple payments without move for the current line's invoice,
                        # as current_amount would not have been enough for _apply_early_payment_discount to apply an EPD.
                        payment_with_move = line.move_id.matched_payment_ids.filtered(lambda pay: pay.move_id and pay.state in valid_payment_states)
                        if payment.currency_id.compare_amounts(payment.amount_signed, current_amount) == 0:
                            payment.action_cancel()
                            body = payment.env._('A payment with entry was created for the related invoice during its reconciliation, replacing this one: %(link)s.',
                                link=payment_with_move._get_html_link(),
                            )
                            payment.message_post(subject=payment.env._('Canceled payment during reconciliation'), body=body)
                        else:
                            payment.invoice_ids -= line.move_id
                            payment.amount -= current_amount
                            body = payment.env._('A payment with entry was created for an invoice previously linked to this payment: %(link)s.\n'
                                     'Its amount was deducted from this payment.',
                                link=payment_with_move._get_html_link(),
                            )
                            payment.message_post(subject=payment.env._('Modified amount during reconciliation'), body=body)
                    elif lines_with_epd:
                        lines_with_epd[0]['payment_lines_ids'] = [Command.set(payment.ids)]

                remaining -= current_amount
                amls_to_create.extend(amls_to_add)

            if remaining:
                partner_account = (
                    payment.partner_id.property_account_payable_id
                    if payment.payment_type == "outbound"
                    else payment.partner_id.property_account_receivable_id
                )
                amls_to_create.append({
                    'name': payment.name,
                    'partner_id': payment.partner_id.id,
                    'account_id': partner_account.id,
                    'currency_id': payment.currency_id.id,
                    'amount_currency': -remaining,
                    'balance': payment.currency_id._convert(from_amount=-remaining, to_currency=company_currency, date=st_line.date),
                    'payment_lines_ids': [Command.set(payment.ids)],
                })
        return amls_to_create, has_exchange_diff
