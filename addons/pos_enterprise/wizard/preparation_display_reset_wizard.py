from odoo import models


class PosPreparationDisplayResetWizard(models.TransientModel):
    _name = 'pos.preparation.display.reset.wizard'
    _description = 'Reset all current order in a preparation display'

    def reset_all_orders(self):
        preparation_display = self.env['pos.prep.display'].search([('id', '=', self.env.context['prep_display_id'])])
        preparation_display.reset()
