# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _set_shop_warning_stock(self, desired_qty, new_qty, save=True):
        """Adapt availability message for rental products."""
        self.ensure_one()
        if not self.is_rental:
            return super()._set_shop_warning_stock(desired_qty, new_qty, save=save)

        warning = _(
            "You asked for %(desired_qty)s %(product_name)s but only %(new_qty)s are available from"
            " %(rental_period)s.",
            desired_qty=desired_qty,
            product_name=self.product_id.name,
            new_qty=new_qty,
            rental_period=self._get_rental_order_line_description()
        )

        if save:
            self.shop_warning = warning

        return warning
