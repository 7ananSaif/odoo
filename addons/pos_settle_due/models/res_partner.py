# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'
    pos_orders_amount_due = fields.Float(string="Sum of customers PoS orders's due amount", compute="_compute_pos_orders_amount_due")
    invoices_amount_due = fields.Float(string="Sum of customers's invoice due amount", compute="_compute_invoices_amount_due")

    def _compute_pos_orders_amount_due(self):
        commercial_partner_ids = {p.id: p.commercial_partner_id.id for p in self}
        # Fetch the total sum of 'customer_due_total' grouped by 'commercial_partner_id'
        pos_orders = self.env['pos.order']._read_group(
            domain=[
                ('commercial_partner_id', 'in', set(commercial_partner_ids.values())),
                ('state', 'in', ['paid', 'done'])
            ],
            groupby=['commercial_partner_id'],
            aggregates=['customer_due_total:sum']
        )

        due_map = {order[0].id: order[1] for order in pos_orders}
        for partner in self:
            partner.pos_orders_amount_due = due_map.get(commercial_partner_ids[partner.id], 0.0)

    def _compute_invoices_amount_due(self):
        commercial_partner_ids = {p.id: p.commercial_partner_id.id for p in self}
        # Fetch the sum of 'pos_amount_unsettled' of unpaid invoices grouped by 'commercial_partner_id'
        invoices = self.env['account.move']._read_group(
            domain=[('commercial_partner_id', 'in', set(commercial_partner_ids.values())),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('move_type', 'in', self.env['account.move'].get_sale_types())],
            groupby=['commercial_partner_id'],
            aggregates=['pos_amount_unsettled:sum']
        )

        due_map = {inv[0].id: inv[1] for inv in invoices}
        for partner in self:
            partner.invoices_amount_due = due_map.get(commercial_partner_ids[partner.id], 0.0)

    def get_total_due(self, config_id):
        config = self.env['pos.config'].browse(config_id)
        pos_payments = self.env['pos.order'].search([
            ('commercial_partner_id', '=', self.commercial_partner_id.id), ('state', '=', 'paid'),
            ('session_id.state', '!=', 'closed')]).mapped('payment_ids')
        total_settled = sum(pos_payments.filtered_domain(
            [('payment_method_id.type', '=', 'pay_later')]).mapped('amount'))

        self_sudo = self
        group_pos_user = self.env.ref('point_of_sale.group_pos_user')
        if group_pos_user in self.env.user.all_group_ids:
            self_sudo = self.sudo()  # allow POS users without accounting rights to settle dues

        total_due = self_sudo.parent_id.total_due if self.parent_id else self_sudo.total_due
        total_due += total_settled
        if self.env.company.currency_id.id != config.currency_id.id:
            pos_currency = config.currency_id
            total_due = self.env.company.currency_id._convert(total_due, pos_currency, self.env.company, fields.Date.today())
        partner = self.env['res.partner']._load_pos_data_read(self, config)[0]
        partner['total_due'] = total_due
        return {
            'res.partner': [partner],
        }

    def get_all_total_due(self, config_id):
        due_amounts = []
        partners = self.exists()
        for partner in partners:
            due_amounts.append(partner.get_total_due(config_id))
        return due_amounts

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        if self.env.user.has_group('account.group_account_readonly') or self.env.user.has_group('account.group_account_invoice'):
            params += ['credit_limit', 'total_due', 'use_partner_credit_limit', 'pos_orders_amount_due', 'invoices_amount_due', 'commercial_partner_id']
        return params

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)

        if config.currency_id != self.env.company.currency_id and (self.env.user.has_group('account.group_account_readonly') or self.env.user.has_group('account.group_account_invoice')):
            for record in read_records:
                record['total_due'] = self.env.company.currency_id._convert(record['total_due'], config.currency_id, self.env.company, fields.Date.today())
        return read_records

    def _compute_has_moves(self):
        super()._compute_has_moves()
        for partner in self.filtered(lambda p: not p.has_moves):
            partner.has_moves = partner.total_due != 0
