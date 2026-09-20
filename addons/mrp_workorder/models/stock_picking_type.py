# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    prefill_shop_floor_lots = fields.Boolean(
        string="Pre fill lot/serial numbers in shop floor moves ",
        help="When enabled, reserved lots for component moves will be displayed in the shop floor. When disabled, lots will always need to be selected manually when processing components in the shop floor.",
        default=False,
    )

    auto_close_production = fields.Boolean(string="Close Manufacturing Orders", help="Allow users to close MO in last work order operation or from the overview tab.", default=True)

    def action_mrp_overview(self):
        routing_count = self.env['stock.picking.type'].search_count([('code', '=', 'mrp_operation')])
        if routing_count == 1:
            return self.env['ir.actions.actions']._for_xml_id('mrp_workorder.action_mrp_display')
        action = self.env['ir.actions.actions']._for_xml_id('mrp_workorder.mrp_stock_picking_type_action')
        action['domain'] = [('code', '=', 'mrp_operation')]
        return action
