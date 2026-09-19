from odoo import fields, models, api, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    delivery_status = fields.Selection([
        ('placed', 'Placed'),
        ('acknowledged', 'Acknowledged'),
        ('food_ready', 'Food Ready'),
        ('dispatched', 'Dispatched'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')], string='Delivery Status', help='Status of the order as provided by UrbanPiper.')
    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Delivery Provider',
        help='Responsible delivery provider for online order, e.g., UberEats, Zomato.'
    )
    delivery_identifier = fields.Char(string='Delivery ID', help='Unique delivery ID provided by UrbanPiper.')
    delivery_json = fields.Json(string='Delivery JSON', help='JSON data of the order.', store=True)
    delivery_rider_json = fields.Json(string='Delivery Rider JSON', help='JSON data of the delivery rider.', store=True)
    prep_time = fields.Integer(
        string='Food Preparation Time',
        help='Preparation time for the food as provided by UrbanPiper.'
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_online_order(self):
        if (self.filtered(lambda o: o.delivery_identifier)):
            raise UserError(_('Online orders cannot be deleted. If needed, reject the order instead or contact the food delivery provider.'))

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['delivery_status', 'delivery_provider_id', 'delivery_identifier', 'prep_time', 'config_id']
