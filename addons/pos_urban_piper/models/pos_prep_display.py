from odoo import models


class PosPrepDisplay(models.Model):
    _inherit = 'pos.prep.display'

    def _get_open_orderlines_in_display(self):
        pdis_orderlines = super()._get_open_orderlines_in_display()
        return pdis_orderlines.filtered(lambda ol: ol.prep_line_id.prep_order_id.pos_order_id.delivery_status in (False, 'acknowledged', 'food_ready', 'cancelled'))

    def _load_preparation_data_models(self):
        res = super()._load_preparation_data_models()
        return res + ['pos.delivery.provider']

    def _get_preparation_display_order_additional_info(self, prep_states, prep_lines, prep_orders):
        self.ensure_one()
        res = super()._get_preparation_display_order_additional_info(prep_states, prep_lines, prep_orders)
        providers = prep_orders.pos_order_id.delivery_provider_id
        res['pos.delivery.provider'] = providers.read(providers._load_pos_preparation_data_fields(), load=False)
        return res
