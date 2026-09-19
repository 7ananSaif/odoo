from odoo import models


class PosPreparationState(models.Model):
    _inherit = 'pos.prep.state'

    def change_state_stage(self, stages, prep_display_id):
        res = super().change_state_stage(stages, prep_display_id)
        self.env['pos.prep.display'].browse(int(prep_display_id))._send_orders_to_customer_display()
        return res
