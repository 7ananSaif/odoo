from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import date_utils

from odoo.addons.hr_expense_stripe.utils import format_amount_from_stripe


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    stripe_id = fields.Char("Stripe transaction ID", readonly=True)

    _check_unique_stripe_id = models.Constraint(
        definition="UNIQUE(stripe_id)",
        message="Only one bank statement can be created from a single stripe transaction"
    )

    @api.model
    def _create_from_stripe_topup(self, tu_object):
        company = self.env.company
        journal = company.stripe_journal_id
        journal_currency = journal.currency_id or journal.company_id.stripe_currency_id
        topup_currency = (
            self.env['res.currency'].with_context(active_test=False).search([('name', 'ilike', tu_object['currency'])], limit=1)
            or journal_currency
        )
        if topup_currency and not topup_currency.active:
            topup_currency.active = True
        amount = format_amount_from_stripe(tu_object['amount'], journal_currency)
        date = date_utils.datetime.fromtimestamp(tu_object['created'])

        transfer_account = company.transfer_account_id
        create_vals = {
            'stripe_id': tu_object['id'],
            'date': date,
            'journal_id': journal.id,
            'payment_ref': _("Stripe Top-up"),
            'amount': amount,
        }
        if transfer_account.active:
            create_vals['counterpart_account_id'] = transfer_account.id  # Hack 'field'

        if topup_currency != journal_currency:
            create_vals.update({
                'foreign_currency_id': topup_currency.id,
                'amount_currency': amount,
                'amount': topup_currency._convert(amount, journal_currency, journal.company_id, date),
            })
        self.with_context(no_retrieve_partner=True).create([create_vals])

    @api.model
    def _create_from_stripe_transaction(self, tr_object):
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        if not card:
            raise UserError(_("A card that doesn't exist on the database was used"))
        amount, amount_currency, journal, journal_currency, merchant_currency = self._get_transaction_data(card, tr_object)
        payment_ref = _(
            "Card ending in %(last_4)s payment to %(merchant_name)s",
            last_4=card.last_4,
            merchant_name=tr_object['merchant_data']['name']
        )
        create_vals = {
            'stripe_id': tr_object['id'],
            'date': date_utils.datetime.fromtimestamp(tr_object['created']),
            'journal_id': journal.id,
            'payment_ref': payment_ref,
            'amount': amount,
        }
        if merchant_currency != journal_currency:
            create_vals.update({
                'foreign_currency_id': merchant_currency.id,
                'amount_currency': amount_currency,
            })

        stmt_line = self.create([create_vals])

        expenses = self.env['hr.expense'].search([('stripe_transaction_id', '=', tr_object['id'])])
        if expenses:
            for expense in expenses:
                stmt_line.move_id.message_post(
                    body=_('Transaction created from %(expense)s', expense=expense._get_html_link(title=expense.name)),
                    message_type='comment',
                )
            if all(expense.account_move_id.origin_payment_id.state == 'in_process' for expense in expenses):
                # Split expenses cases, we only want to reconcile if everything posted
                expenses._reconcile_stripe_payments(existing_statement_lines=stmt_line)

    def _update_from_stripe_transaction(self, tr_object):
        self.ensure_one()
        card = self.env['hr.expense.stripe.card'].search([('stripe_id', '=', tr_object['card'])], limit=1)
        amount, amount_currency, _journal, journal_currency, merchant_currency = self._get_transaction_data(card, tr_object)

        update_vals = {}
        if self.currency_id.compare_amounts(self.amount, amount) != 0:
            update_vals['amount'] = amount

        if merchant_currency != journal_currency:
            if self.foreign_currency_id != merchant_currency:
                update_vals['foreign_currency_id'] = merchant_currency.id
            if merchant_currency.compare_amounts(self.amount_currency, amount_currency) != 0:
                update_vals['amount_currency'] = amount_currency

        if update_vals:
            self.write(update_vals)

    ##################
    # Helper methods #
    ##################
    @api.model
    def _get_transaction_data(self, card, tr_object):
        journal = card.journal_id
        journal_currency = journal.currency_id or journal.stripe_currency_id
        amount = amount_currency = format_amount_from_stripe(tr_object['amount'], card.currency_id)
        merchant_currency = (
            self.env['res.currency'].with_context(active_test=False).search([('name', 'ilike', tr_object['merchant_currency'])], limit=1)
            or journal_currency
        )
        if merchant_currency and not merchant_currency.active:
            merchant_currency.active = True
        if merchant_currency != journal_currency:
            amount_currency = format_amount_from_stripe(tr_object['merchant_amount'], merchant_currency)
        return amount, amount_currency, journal, journal_currency, merchant_currency
