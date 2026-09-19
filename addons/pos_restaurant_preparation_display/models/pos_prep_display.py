from odoo import models


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    def _load_preparation_data_models(self):
        res = super()._load_preparation_data_models()
        return res + ['restaurant.table', 'restaurant.order.course']

    def _get_preparation_display_order_additional_info(self, prep_states, prep_lines, prep_orders):
        self.ensure_one()
        res = super()._get_preparation_display_order_additional_info(prep_states, prep_lines, prep_orders)
        tables = prep_orders.pos_order_id.table_id
        res['restaurant.table'] = tables.read(tables._load_pos_preparation_data_fields(), load=False)
        res['restaurant.order.course'] = prep_orders.pos_course_id.read(prep_orders.pos_course_id._load_pos_preparation_data_fields(), load=False)
        return res
