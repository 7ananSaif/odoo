# -*- coding: utf-8 -*-
# Part of Odoo. See ICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockReturnPickingLine(models.TransientModel):
    _inherit = 'stock.return.picking.line'

    picking_id = fields.Many2one('stock.picking', related='wizard_id.picking_id', export_string_translation=False)  # used for warnings


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    partner_id = fields.Many2one('res.partner', related="ticket_id.partner_id", string="Customer")
    ticket_id = fields.Many2one('helpdesk.ticket')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order',
        domain="[('order_line.product_id.type', '!=', 'service'), ('picking_ids.state', '=', 'done'), ('id', 'in', suitable_sale_order_ids)]",
        compute='_compute_sale_order_id', readonly=False)
    picking_id = fields.Many2one(domain="[('id', 'in', suitable_picking_ids)]", compute='_compute_picking_id', precompute=True, readonly=False, store=True)
    suitable_picking_ids = fields.Many2many('stock.picking', compute='_compute_suitable_picking_ids')
    suitable_sale_order_ids = fields.Many2many('sale.order', compute='_compute_suitable_sale_orders')

    @api.depends('picking_id')
    def _compute_sale_order_id(self):
        for r in self:
            r.sale_order_id = r.picking_id.sale_id

    @api.depends('sale_order_id')
    def _compute_picking_id(self):
        for r in self:
            if not r.picking_id:
                domain = [
                    ('state', '=', 'done'),
                    ('partner_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                ]
                if r.ticket_id.product_id:
                    domain += [('move_line_ids.product_id', '=', r.ticket_id.product_id.id)]
                picking = self.env['stock.picking'].search(domain, limit=1, order='id desc')
                if picking:
                    r.picking_id = picking
            if r.sale_order_id:
                picking = r.sale_order_id.picking_ids.filtered(lambda p: p.id in r.suitable_picking_ids.ids) \
                    if r.sale_order_id.picking_ids \
                    else False
                r.picking_id = picking[0] if picking else False

    @api.depends('ticket_id.partner_id.commercial_partner_id', 'sale_order_id')
    def _compute_suitable_picking_ids(self):
        for r in self:
            if not r.ticket_id and not r.sale_order_id:
                r.suitable_picking_ids = False
                continue

            domain = [('state', '=', 'done'), ('picking_type_id.code', '!=', 'incoming')]
            if r.sale_order_id:
                domain += [('id', 'in', r.sale_order_id.picking_ids._origin.ids)]
            elif r.partner_id:
                domain += [('partner_id', 'child_of', r.partner_id.commercial_partner_id._origin.id)]
            if r.ticket_id.product_id:
                domain += [('move_line_ids.product_id', '=', r.ticket_id.product_id._origin.id)]
            r.suitable_picking_ids = self.env['stock.picking'].with_context(active_test=False).search(domain)

    @api.depends('ticket_id.partner_id.commercial_partner_id')
    def _compute_suitable_sale_orders(self):
        for r in self:
            if not r.ticket_id:
                r.suitable_sale_order_ids = False
                continue
            domain = [('state', '=', 'sale')]
            if r.ticket_id.product_id:
                domain += [('order_line.product_id', '=', r.ticket_id.product_id._origin.id)]
            if r.ticket_id.partner_id:
                domain += [
                    '|',
                        ('partner_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                        ('partner_shipping_id.commercial_partner_id', '=', r.ticket_id.partner_id.commercial_partner_id.id),
                ]
            r.suitable_sale_order_ids = self.env['sale.order'].search(domain)

    def _prepare_picking_default_values(self):
        if not self.picking_id and self.ticket_id:
            # Take return picking type of outgoing type if found, else take the incoming type
            picking_type = self.env['stock.picking.type'].search([
                ('company_id', '=', self.ticket_id.company_id.id),
                ('code', '=', 'outgoing'),
            ], limit=1).return_picking_type_id

            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    ('company_id', '=', self.ticket_id.company_id.id),
                    ('code', '=', 'incoming'),
                ], limit=1)

            return {
                'move_ids': [],
                'state': 'draft',
                'return_id': False,
                'origin': self.env._('Ticket: %(ticket_name)s', ticket_name=self.ticket_id.name),
                'partner_id': self.ticket_id.partner_id.address_get(['delivery'])['delivery'],
                'ticket_id': self.ticket_id.id,
                'picking_type_id': picking_type.id,
            }
        return super()._prepare_picking_default_values()

    def _create_return(self):
        new_picking = super()._create_return()

        if ticket_id := self.ticket_id or self.env['helpdesk.ticket'].sudo().search([('picking_ids', 'in', new_picking.id)], limit=1):
            ticket_id.picking_ids |= new_picking
        return new_picking
