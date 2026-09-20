from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import format_date
from odoo.addons.equity.utils import safe_division


class EquityValuation(models.Model):
    _name = 'equity.valuation'
    _inherit = ['mail.thread']
    _description = "Valuation"

    event = fields.Selection(selection=[('audit', "Audit"), ('transaction', "Transaction")], default='transaction', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one(
        'res.partner',
        string="Company",
        default=lambda self: self.env.company.partner_id,
        domain=[('is_company', '=', True)],
        required=True,
        index='btree',
    )
    equity_currency_id = fields.Many2one('res.currency', related='partner_id.equity_currency_id')

    securities = fields.Float(string="# Securities", compute='_compute_securities')
    shares = fields.Float(string="# Shares", compute='_compute_securities')
    security_price = fields.Monetary(string="Price per Security", currency_field='equity_currency_id', compute='_compute_security_price')
    share_price = fields.Float(
        string="Price per Share",
        digits=0,
        compute='_compute_share_price',
        inverse='_inverse_compute_share_price',
    )
    valuation = fields.Monetary(currency_field='equity_currency_id')

    attachment_ids = fields.One2many('ir.attachment', 'res_id', string="Attachments")
    attachment_number = fields.Integer(compute='_compute_attachment_number')

    @api.depends('partner_id', 'date')
    def _compute_securities(self):
        for valuation in self:
            cap_table_entries = self.env['equity.cap.table'].with_context(current_date=valuation.date).search([
                ('partner_id', '=', valuation.partner_id.id),
            ])
            shares = sum(cap_table_entries.filtered(lambda cte: cte.securities_type == 'shares').mapped('securities'))
            options = sum(cap_table_entries.filtered(lambda cte: cte.securities_type == 'options').mapped('securities'))
            valuation.securities = shares + options
            valuation.shares = shares

    @api.depends('valuation', 'securities')
    def _compute_security_price(self):
        for valuation in self:
            valuation.security_price = safe_division(valuation.valuation, valuation.securities)

    @api.depends('valuation', 'shares')
    def _compute_share_price(self):
        for valuation in self:
            valuation.share_price = safe_division(valuation.valuation, valuation.shares)

    @api.onchange('share_price')
    def _inverse_compute_share_price(self):
        for valuation in self:
            valuation.valuation = valuation.share_price * valuation.shares

    @api.depends('partner_id.display_name', 'equity_currency_id', 'valuation')
    def _compute_display_name(self):
        for valuation in self:
            if valuation.partner_id:
                valuation.display_name = self.env._(
                    "%(partner_name)s %(amount)s",
                    partner_name=valuation.partner_id.display_name,
                    amount=valuation.equity_currency_id.format(valuation.valuation),
                )
            else:
                valuation.display_name = ""

    def _compute_attachment_number(self):
        valuation_attachment_counts = dict(self.env['ir.attachment']._read_group(
            domain=[
                ('res_model', '=', 'equity.valuation'),
                ('res_id', 'in', self.ids),
            ],
            groupby=['res_id'],
            aggregates=['__count'],
        ))
        for valuation in self:
            valuation.attachment_number = valuation_attachment_counts.get(valuation.id, 0)

    @api.model
    def get_valuation_chart_data(self, data_function, freq='month', limit=12):
        today = fields.Date.today()
        date_format = 'MMM d, y' if freq == 'day' else 'yyyy' if freq == 'year' else 'MMM yyyy'

        def past_dates(freq, limit):
            if freq not in {'year', 'month', 'day'}:
                freq = 'month'

            for i in range(limit - 2, -2, -1):
                if freq == 'year':
                    date = (today - relativedelta(years=i)).replace(month=1, day=1)
                elif freq == 'month':
                    date = (today - relativedelta(months=i)).replace(day=1)
                elif freq == 'day':
                    date = today - relativedelta(days=i)
                    date = date.replace(hour=0, minute=0, second=0, microsecond=0)

                yield date

        return {
            format_date(self.env, past_date, date_format=date_format): data_function(past_date) for past_date in past_dates(freq, limit)
        }

    @api.model
    def get_all_partners_valuation_chart_data(self):
        valuations = self.search([], order='date DESC')
        partners = valuations.partner_id
        valuations_per_partner = valuations.grouped('partner_id')

        def chart_data_function(past_date):
            res = []
            for partner in partners:
                partner_valuations = valuations_per_partner.get(partner).filtered(lambda v: v.date <= past_date)
                valuation = partner_valuations[0].valuation if partner_valuations else 0
                res.append(valuation)
            return res

        labels = partners.mapped('display_name')
        return {
            'labels': labels,
            'data': self.get_valuation_chart_data(data_function=chart_data_function)
        }
