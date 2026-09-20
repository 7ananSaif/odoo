from odoo import api, models
from odoo.fields import Domain


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _payment_request_from_kiosk(self, order):
        if not self.iot_device_id:
            return super()._payment_request_from_kiosk(order)
        return "success"

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        domain = super()._load_pos_self_data_domain(data, config)
        if config.self_ordering_mode == 'kiosk':
            domain = Domain.OR([
                [('iot_device_id', '!=', False), ('id', 'in', config.payment_method_ids.ids)],
                domain
            ])
        return domain
