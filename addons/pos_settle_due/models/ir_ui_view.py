from odoo import models, api


class IrUiView(models.Model):
    _name = 'ir.ui.view'
    _inherit = ['pos.load.mixin', 'ir.ui.view']

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'name']

    @api.model
    def _load_pos_data_search_read(self, data, config):
        return [{
            "id": self.env.ref('pos_settle_due.customer_due_pos_order_list_view').id,
            "name": "customer_due_pos_order_list_view",
        }, {
            "id": self.env.ref('pos_settle_due.due_account_move_list_view').id,
            "name": "due_account_move_list_view",
        }]
