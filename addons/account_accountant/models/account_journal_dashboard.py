from odoo import models
from odoo.tools import formatLang


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def action_open_reconcile(self):
        self.ensure_one()

        if self.type in ('bank', 'cash', 'credit'):
            return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
                default_context={
                    'default_journal_id': self.id,
                    'search_default_journal_id': self.id,
                    'search_default_not_matched': True,
                },
            )
        else:
            # Open reconciliation view for customers/suppliers
            return self.env['ir.actions.act_window']._for_xml_id('account_accountant.action_move_line_posted_unreconciled')

    def action_open_to_check(self):
        self.ensure_one()
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_to_check': True,
                'search_default_journal_id': self.id,
                'default_journal_id': self.id,
            },
        )

    def action_open_bank_transactions(self):
        self.ensure_one()
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_journal_id': self.id,
                'default_journal_id': self.id
             },
            kanban_first=False,
        )

    def action_open_reconcile_statement(self):
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            default_context={
                'search_default_statement_id': self.env.context.get('statement_id'),
                'default_journal_id': self.id,
            },
        )

    def open_invalid_statements_action(self):
        # EXTENDS account
        self.ensure_one()
        if self.env['account.bank.statement'].search([('journal_id', '=', self.id), ('first_line_index', '=', False)], limit=1):
            # Empty statements are not shown in the bank reco widget
            return super().open_invalid_statements_action()
        return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
            extra_domain=[('line_ids.account_id', '=', self.default_account_id.id)],
            default_context={
                'default_journal_id': self.id,
                'search_default_journal_id': self.id,
                'search_default_invalid_statement': True,
            },
            kanban_first=False,
        )

    def open_action(self):
        # EXTENDS account
        # set default action for liquidity journals in dashboard

        if self.type in ('bank', 'cash', 'credit') and not self.env.context.get('action_name'):
            self.ensure_one()
            return self.env['account.bank.statement.line']._action_open_bank_reconciliation_widget(
                default_context={
                    'default_journal_id': self.id,
                    'search_default_journal_id': self.id,
                },
            )
        return super().open_action()

    def get_total_journal_amount(self):
        balance = ''
        if self.exists() and any(
                company in self.company_id._accessible_branches() for company in self.env.companies):
            balance = formatLang(
                self.env,
                self.current_statement_balance,
                currency_obj=self.currency_id or self.company_id.sudo().currency_id,
            )
        return {'balance_amount': balance, 'has_invalid_statements': self.has_invalid_statements}
