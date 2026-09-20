from odoo import api, models


class RestaurantOrderCourse(models.Model):
    _inherit = 'restaurant.order.course'

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['fired', 'fired_date']
