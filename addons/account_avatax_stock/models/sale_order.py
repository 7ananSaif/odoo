from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_line_data_for_external_taxes(self):
        """ Override to set the originating warehouse per line. """
        res = super()._get_line_data_for_external_taxes()
        for line in res:
            line['warehouse_id'] = line['base_line']['record'].warehouse_id
            line['shipping_partner'] = self.partner_shipping_id or self.partner_id
        return res
