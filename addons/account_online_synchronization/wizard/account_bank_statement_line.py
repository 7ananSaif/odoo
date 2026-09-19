from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountBankStatementLineTransient(models.TransientModel):
    _name = 'account.bank.statement.line.transient'
    _description = "Transient model for bank statement line"
    _order = 'date asc'

    sequence = fields.Integer(default=1)
    date = fields.Date()
    amount = fields.Monetary(readonly=True)
    online_transaction_identifier = fields.Char(readonly=True)
    payment_ref = fields.Char(readonly=True)
    account_number = fields.Char(readonly=True)
    partner_name = fields.Char(readonly=True)
    transaction_details = fields.Json(readonly=True)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('posted', 'Posted'),
        ],
        default='posted',
        readonly=True,
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        readonly=True,
    )
    online_account_id = fields.Many2one(
        related='journal_id.account_online_account_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related='journal_id.company_id.currency_id',
        readonly=True,
    )
    company_id = fields.Many2one(comodel_name='res.company')

    foreign_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Foreign Currency",
    )

    amount_currency = fields.Monetary(
        string="Amount in Currency",
        currency_field='foreign_currency_id',
    )

    def action_import_transactions(self):
        # This action could be call on multiple lines.
        if not self:
            raise UserError(_("Please select first the transactions you wish to import."))

        if self.filtered(lambda line: line.state == 'pending'):
            raise UserError(_("You cannot import pending transactions."))

        fields_to_read = [
            'date',
            'amount',
            'online_transaction_identifier',
            'payment_ref',
            'account_number',
            'partner_name',
            'transaction_details',
            'journal_id',
            'online_account_id',
            'company_id',
            'foreign_currency_id',
            'amount_currency',
        ]
        transactions_to_import = self.read(fields=fields_to_read, load=None)
        self.env['account.bank.statement.line']._online_sync_bank_statement(transactions_to_import, self.online_account_id)
        return self.env["ir.actions.act_window"]._for_xml_id('account.open_account_journal_dashboard_kanban')

    @api.model_create_multi
    def create(self, vals_list):
        # When iso20022 module is installed, the _format_transaction will keep the end_to_end_uuid in the transaction
        # but the field is not present in this transient model
        for vals in vals_list:
            vals.pop('end_to_end_uuid', None)

        return super().create(vals_list)
