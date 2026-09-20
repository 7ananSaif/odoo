# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    settled_order_id = fields.Many2one('pos.order', string='Settled Order', index='btree_not_null')
    settled_invoice_id = fields.Many2one('account.move', string='Settled Invoice', index='btree_not_null')

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        params += ['settled_order_id', 'settled_invoice_id']
        return params

    def _prepare_tax_base_line_values(self):
        # We don't want to create tax lines for settled and deposit orderlines (except on invoice to appear on it)
        if self.env.context.get('invoicing'):
            return super()._prepare_tax_base_line_values()
        lines = self.filtered(lambda line: not line._is_settle_or_deposit())
        return super(PosOrderLine, lines)._prepare_tax_base_line_values()

    def _is_settle_or_deposit(self):
        self.ensure_one()
        return self.settled_order_id or self.settled_invoice_id or self.product_id == self.order_id.config_id.deposit_product_id
