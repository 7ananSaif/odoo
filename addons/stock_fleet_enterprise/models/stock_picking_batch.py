from odoo import _, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_picking_map_view(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock_fleet_enterprise.stock_picking_action_view_map')
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        return action

    def action_open_batch_from_gantt_view(self):
        """ Method to open the batch form view of the current record from the Gantt view.
        """
        self.ensure_one()
        view_id = self.env.ref('stock_fleet_enterprise.stock_picking_batch_view_form_plan_batch').id
        return {
            'name': _('Plan Batch'),
            'res_model': 'stock.picking.batch',
            'view_mode': 'form',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }
