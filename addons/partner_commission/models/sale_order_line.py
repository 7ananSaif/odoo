from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_additional_domain_for_purchase_order_line(self):
        if self.order_id.referrer_id:
            return []
        return super()._get_additional_domain_for_purchase_order_line()
