from odoo import models, api


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    def _get_preparation_display_order_additional_info(self, prep_states, prep_lines, prep_orders):
        self.ensure_one()
        res = super()._get_preparation_display_order_additional_info(prep_states, prep_lines, prep_orders)
        res['pos.config'] = self._get_pos_config_ids().read(['id', 'name', 'has_paper', 'use_presets'], load=False)
        return res

    def _paper_status_change(self, pos_config):
        preparation_displays = self.search(['|', ('pos_config_ids', 'in', pos_config.ids), ('pos_config_ids', '=', False)])
        for p_dis in preparation_displays:
            p_dis._send_load_printer_status_message(pos_config.read(['id', 'name', 'has_paper'])[0])

    def _send_load_printer_status_message(self, pos_config):
        self.ensure_one()
        self._notify('PAPER_STATUS', pos_config)

    @api.model
    def change_paper_status(self, config_id, has_paper):
        pos_config = self.env['pos.config'].search([('id', '=', config_id)])
        pos_config.write({'has_paper': has_paper})
