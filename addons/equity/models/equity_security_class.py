from odoo import api, models, fields
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_repr


class EquitySecurityClass(models.Model):
    _name = 'equity.security.class'
    _description = "Security Class"
    _order = 'sequence ASC, name ASC, id ASC'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, required=True)
    class_type = fields.Selection(
        string="Type",
        selection=[
            ('shares', "Shares"),
            ('options', "Options"),
        ],
        default='shares',
        required=True,
    )
    share_votes = fields.Integer(
        string="Votes per Share",
        required=True,
        compute='_compute_share_votes', store=True, readonly=False, precompute=True,
    )
    dividend_payout = fields.Boolean(compute='_compute_dividend_payout', store=True, readonly=False, precompute=True)

    @api.constrains('class_type')
    def _check_existing_transactions(self):
        transactions_dict = dict(self.env['equity.transaction']._read_group(
            domain=[
                ('security_class_id', 'in', self.ids),
            ],
            groupby=['security_class_id'],
            aggregates=['__count'],
        )) | dict(self.env['equity.transaction']._read_group(
            domain=[
                ('destination_class_id', 'in', self.ids),
            ],
            groupby=['destination_class_id'],
            aggregates=['__count'],
        ))
        for security_class in self:
            if transactions_dict.get(security_class, 0):
                raise ValidationError(self.env._("Cannot change security class type because it has linked transactions"))

    @api.depends('class_type')
    def _compute_share_votes(self):
        for security_class in self:
            security_class.share_votes = 1 if security_class.class_type == 'shares' else 0

    @api.depends('class_type')
    def _compute_dividend_payout(self):
        for security_class in self:
            security_class.dividend_payout = security_class.class_type == 'shares'

    @api.depends('name')
    @api.depends_context('transaction_id', 'transaction_type', 'transaction_date', 'partner_id', 'subscriber_id', 'seller_id', 'formatted_display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('formatted_display_name'):
            return
        securities_per_class = self._get_securities_per_class()
        for security_class in self:
            if (remaining := securities_per_class.get(security_class)) is not None:
                security_class.display_name += f" \t--{float_repr(remaining, 2)}--"

    def _get_securities_per_class(self):
        transaction_id = self.env.context.get('transaction_id')
        transaction_type = self.env.context.get('transaction_type')
        transaction_date = self.env.context.get('transaction_date')
        partner_id = self.env.context.get('partner_id')
        subscriber_id = self.env.context.get('subscriber_id')
        seller_id = self.env.context.get('seller_id')

        holder_id = None
        if transaction_type == 'transfer':
            holder_id = seller_id
        else:
            holder_id = subscriber_id

        if (
            not transaction_type
            or transaction_type == 'issuance'
            or not transaction_date
            or not partner_id
        ):
            return {}

        securities_per_class = dict(self.env['equity.cap.table'].with_context(
            current_transaction_id=transaction_id,
        )._read_group(
            domain=[
                ('partner_id', '=', partner_id),
                ('holder_id', '=', holder_id),
                ('security_class_id', 'in', self.ids),
            ],
            groupby=['security_class_id'],
            aggregates=['securities:sum'],
        ))

        return {
            security_class: securities_per_class.get(security_class, 0)
            for security_class in self
        }

    def _get_cap_table_data(self):
        self.ensure_one()
        return {
            'display_name': self.display_name,
        }
