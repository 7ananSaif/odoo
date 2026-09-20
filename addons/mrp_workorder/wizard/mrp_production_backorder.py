# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MrpProductionBackorder(models.TransientModel):
    _inherit = 'mrp.production.backorder'

    def action_close_mo(self):
        if wo_id := self.env.context.get('workorder_id_to_finish', False):
            return self._finish_workorder(self.env['mrp.workorder'].browse(wo_id), self.env['mrp.production'])
        return super().action_close_mo()

    def action_backorder(self):
        if wo_id := self.env.context.get('workorder_id_to_finish', False):
            always_backorder_mo_ids = self.env.context.get('always_backorder_mo_ids', [])
            mo_ids_to_backorder = self.mrp_production_backorder_line_ids.filtered(lambda l: l.to_backorder).mrp_production_id.ids + always_backorder_mo_ids
            return self._finish_workorder(self.env['mrp.workorder'].browse(wo_id), self.env['mrp.production'].browse(mo_ids_to_backorder))
        return super().action_backorder()

    def _finish_workorder(self, workorder_to_finish, productions_to_backorder):

        backorders = productions_to_backorder and productions_to_backorder._split_productions()
        backorders = backorders - productions_to_backorder

        # It is prudent to reserve any quantity that has become available to the backorder
        # production's move_raw_ids after the production which spawned them has been marked done.
        backorders_to_assign = backorders.filtered(
            lambda order:
            order.picking_type_id.reservation_method == 'at_confirm'
        )
        for backorder in backorders_to_assign:
            backorder.action_assign()

        # as we are bypassing the normal record_production flow, let's finish it
        return workorder_to_finish.post_record_production(backorders)
