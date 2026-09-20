from dateutil.relativedelta import relativedelta

from odoo import api, models, fields
from odoo.exceptions import ValidationError


class EquityTransaction(models.Model):
    _name = 'equity.transaction'
    _inherit = ['mail.thread']
    _description = "Equity Transaction"

    transaction_type = fields.Selection(
        string="Transaction Type",
        selection=[
            ('issuance', "Issuance"),
            ('transfer', "Transfer"),
            ('exercise', "Option Exercise"),
            ('cancellation', "Cancellation"),
        ],
        default='issuance',
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Company",
        default=lambda self: self.env.company.partner_id,
        domain=[('is_company', '=', True)],
        required=True,
        index='btree',
    )
    equity_currency_id = fields.Many2one(comodel_name='res.currency', string="Currency", related='partner_id.equity_currency_id')
    date = fields.Date(default=fields.Date.context_today, required=True)
    expiration_date = fields.Date(
        string="Expiration",
        compute='_compute_expiration_date', store=True, readonly=False,
        tracking=True,
    )
    expiration_diff = fields.Text(compute='_compute_expiration_diff')
    securities = fields.Float(
        string="# Securities",
        required=True,
        tracking=True,
    )
    security_class_id = fields.Many2one(comodel_name='equity.security.class', string="Class", required=True)
    securities_type = fields.Selection(related='security_class_id.class_type')
    destination_class_id = fields.Many2one(comodel_name='equity.security.class', domain=[('class_type', '=', 'shares')])
    invalid_securities_error = fields.Text(compute='_compute_invalid_securities_error')
    security_price = fields.Float(
        string="Price per Security",
        digits=0,
        compute='_compute_security_price', store=True, readonly=False,
        tracking=True,
    )
    transfer_amount = fields.Monetary(
        string="Total",
        currency_field='equity_currency_id',
        compute='_compute_transfer_amount',
        inverse='_inverse_compute_transfer_amount',
    )
    notes = fields.Text()

    seller_id = fields.Many2one(comodel_name='res.partner', string="Seller", tracking=True)
    subscriber_id = fields.Many2one(
        comodel_name='res.partner',
        string="Subscriber",
        tracking=True,
        help="Recipient of the securities of the transaction.",
    )
    subscriber_id_placeholder = fields.Char(compute='_compute_subscriber_id_placeholder')

    seller_name = fields.Char(compute='_compute_owners_names')
    subscriber_name = fields.Char(compute='_compute_owners_names')

    attachment_ids = fields.One2many(comodel_name='ir.attachment', inverse_name='res_id', string="Attachments")
    attachment_number = fields.Integer(compute='_compute_attachment_number')

    @api.constrains('seller_id', 'subscriber_id')
    def _check_seller_and_subscriber(self):
        for record in self:
            if record.transaction_type == 'transfer' and record.seller_id.id == record.subscriber_id.id:
                raise ValidationError(self.env._("Seller and Buyer must be different."))
            if record.securities_type == 'shares' and not record.subscriber_id:
                raise ValidationError(self.env._("Shares transactions must have a subscriber"))

    @api.constrains('partner_id', 'transaction_type', 'subscriber_id', 'seller_id', 'security_class_id', 'securities')
    def _check_invalid_securities_error(self):
        for record in self:
            if record.invalid_securities_error:
                raise ValidationError(record.invalid_securities_error)

    @api.constrains('security_class_id', 'transaction_type')
    def _check_transaction_type(self):
        for record in self:
            if record.transaction_type == 'exercise':
                if record.security_class_id.class_type != 'options':
                    raise ValidationError(self.env._("Can only exercise options, please select an options class"))
                if record.destination_class_id.class_type != 'shares':
                    raise ValidationError(self.env._("Exercise transactions must have a destination 'Share' class"))
            elif record.destination_class_id:
                raise ValidationError(self.env._("Destination class can only be set in exercise transactions."))

            if record.transaction_type != 'transfer' and record.seller_id:
                raise ValidationError(self.env._("Seller id can only be set in transfer transactions."))

    @api.depends('date')
    def _compute_expiration_date(self):
        for transaction in self.filtered(lambda t: t.date):
            transaction.expiration_date = transaction.date.replace(year=transaction.date.year + 3)

    @api.depends('transaction_type', 'securities', 'expiration_date', 'security_class_id.class_type')
    def _compute_expiration_diff(self):
        def diff_text(diff_val, singular_diff_type, plural_diff_type):
            diff_type = plural_diff_type if diff_val != 1 else singular_diff_type
            return f"({diff_val} {diff_type} {self.env._('remaining')})"

        self.expiration_diff = False
        for transaction in self.filtered(lambda t: t.transaction_type == 'issuance' and t.securities_type == 'options'):
            if transaction.securities <= 0:
                transaction.expiration_diff = self.env._("(Non-positive options don't expire)")
                continue

            today = fields.Date.today()
            if transaction.expiration_date and transaction.expiration_date >= today:
                diff = relativedelta(transaction.expiration_date, today)
                if diff.years >= 1:
                    transaction.expiration_diff = diff_text(diff.years, self.env._("year"), self.env._("years"))
                elif diff.months >= 1:
                    transaction.expiration_diff = diff_text(diff.months, self.env._("month"), self.env._("months"))
                else:
                    transaction.expiration_diff = diff_text(diff.days, self.env._("day"), self.env._("days"))
            elif transaction.expiration_date:
                transaction.expiration_diff = self.env._("(expired)")
            else:
                transaction.expiration_diff = ""

    @api.depends('transaction_type', 'securities_type', 'partner_id', 'subscriber_id', 'seller_id', 'security_class_id', 'securities')
    def _compute_invalid_securities_error(self):
        self.invalid_securities_error = False
        for transaction in self.filtered(lambda t: t.partner_id and t.security_class_id):
            if transaction.securities <= 0:
                transaction.invalid_securities_error = self.env._("Securities must be positive")
                continue

            if transaction.transaction_type == 'issuance':
                continue

            cap_table_entries = self.env['equity.cap.table'].with_context(current_transaction_id=transaction.id).search([
                ('partner_id', '=', transaction.partner_id.id),
                ('holder_id', 'in', (transaction.subscriber_id.id, transaction.seller_id.id)),
                ('security_class_id', '=', transaction.security_class_id.id),
            ])

            subscriber_securities = sum(cap_table_entries.filtered(lambda cte: cte.holder_id == transaction.subscriber_id).mapped('securities'))
            seller_securities = sum(cap_table_entries.filtered(lambda cte: cte.holder_id == transaction.seller_id).mapped('securities'))

            if (
                transaction.transaction_type == 'cancellation' and
                transaction.securities_type == 'shares' and
                subscriber_securities - transaction.securities < 0
            ):
                transaction.invalid_securities_error = self.env._(
                    "Only %(subscriber_shares)s %(security_class_name)s shares available for cancellation",
                    subscriber_shares=subscriber_securities,
                    security_class_name=transaction.security_class_id.name,
                )
            elif (
                transaction.transaction_type == 'cancellation' and
                transaction.securities_type == 'options' and
                subscriber_securities - transaction.securities < 0
            ):
                transaction.invalid_securities_error = self.env._(
                    "Only %(subscriber_options)s %(security_class_name)s options available for cancellation",
                    subscriber_options=subscriber_securities,
                    security_class_name=transaction.security_class_id.name,
                )
            elif (
                transaction.transaction_type == 'exercise' and
                subscriber_securities - transaction.securities < 0
            ):
                transaction.invalid_securities_error = self.env._(
                    "Only %(subscriber_options)s %(security_class_name)s options available for exercise",
                    subscriber_options=subscriber_securities,
                    security_class_name=transaction.security_class_id.name,
                )
            elif (
                transaction.transaction_type == 'transfer' and
                transaction.securities_type == 'shares' and
                seller_securities - transaction.securities < 0
            ):
                transaction.invalid_securities_error = self.env._(
                    "Only %(seller_shares)s %(security_class_name)s shares available for transfer",
                    seller_shares=seller_securities,
                    security_class_name=transaction.security_class_id.name,
                )
            elif (
                transaction.transaction_type == 'transfer' and
                transaction.securities_type == 'options' and
                seller_securities - transaction.securities < 0
            ):
                transaction.invalid_securities_error = self.env._(
                    "Only %(seller_options)s %(security_class_name)s options available for transfer",
                    seller_options=seller_securities,
                    security_class_name=transaction.security_class_id.name,
                )

    @api.depends('date', 'partner_id')
    def _compute_security_price(self):
        for transaction in self.filtered(lambda t: not bool(self._origin.id)):  # only set security price for newly created records
            transaction.security_price = self.search([
                ('partner_id', '=', transaction.partner_id.id),
                ('date', '<', transaction.date),
            ], order='date DESC', limit=1).security_price

    @api.depends('securities', 'security_price')
    def _compute_transfer_amount(self):
        for transaction in self:
            transaction.transfer_amount = transaction.securities * transaction.security_price

    @api.onchange('securities', 'transfer_amount')
    def _inverse_compute_transfer_amount(self):
        for transaction in self.filtered(lambda t: t.securities):
            transaction.security_price = transaction.transfer_amount / transaction.securities

    @api.onchange('transaction_type')
    def _onchange_transaction_type(self):
        for transaction in self:
            if transaction.transaction_type != 'transfer':
                transaction.seller_id = False
            if transaction.transaction_type != 'exercise':
                transaction.destination_class_id = False

    @api.depends('seller_id.name', 'subscriber_id.name')
    def _compute_owners_names(self):
        for transaction in self:
            transaction.seller_name = transaction.seller_id.name or self.env._("Option Pool")
            transaction.subscriber_name = transaction.subscriber_id.name or self.env._("Option Pool")

    def _compute_attachment_number(self):
        transaction_attachment_counts = dict(self.env['ir.attachment']._read_group(
            domain=[
                ('res_model', '=', 'equity.transaction'),
                ('res_id', 'in', self.ids),
            ],
            groupby=['res_id'],
            aggregates=['__count'],
        ))
        for transaction in self:
            transaction.attachment_number = transaction_attachment_counts.get(transaction.id, 0)

    @api.depends('security_class_id.class_type')
    def _compute_subscriber_id_placeholder(self):
        for transaction in self:
            if transaction.securities_type == 'options':
                transaction.subscriber_id_placeholder = self.env._("Option Pool")
            else:
                transaction.subscriber_id_placeholder = ""

    @api.depends('transaction_type', 'securities', 'security_class_id.name')
    def _compute_display_name(self):
        type_values = dict(self._fields['transaction_type']._description_selection(self.env))
        for transaction in self:
            if transaction.transaction_type and transaction.securities and transaction.security_class_id:
                transaction.display_name = self.env._(
                    "%(transaction_type)s %(securities).2f %(class_name)s",
                    transaction_type=type_values.get(transaction.transaction_type),
                    securities=transaction.securities,
                    class_name=transaction.security_class_id.name,
                )
            else:
                transaction.display_name = ""

    @api.model_create_multi
    def create(self, vals_list):
        transactions = super().create(vals_list)
        self.env['equity.cap.table'].invalidate_model()
        return transactions

    def write(self, vals):
        transactions = super().write(vals)
        self.env['equity.cap.table'].invalidate_model()
        return transactions

    def action_transaction_seller_send(self):
        return self.action_transaction_send(for_seller=True)

    def action_transaction_subscriber_send(self):
        return self.action_transaction_send()

    def action_transaction_send(self, for_seller=False):
        self.ensure_one()
        holder = self.seller_id if for_seller else self.subscriber_id
        if not holder:
            holder_type = self.env._("seller") if for_seller else self.env._("subscriber")
            raise ValidationError(self.env._("No %s was set!", holder_type))
        return holder.action_partner_equity_send(linked_transaction=self)
