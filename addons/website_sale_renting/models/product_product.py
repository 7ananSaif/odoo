# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import timezone

from odoo import models
from odoo.http import request


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _website_show_quick_add(self):
        return super()._website_show_quick_add() and self._can_be_added_to_current_cart()

    def _is_add_to_cart_allowed(self):
        return super()._is_add_to_cart_allowed() and self._can_be_added_to_current_cart()

    # TODO VFE: clean mess someday, too many methods to check product can be added or not
    # TODO provide a way to return error message instead, cause 'product doesn't exist' is bof bof
    def _can_be_added_to_current_cart(self):
        # Overnight products can only be added to:
        # - an empty cart
        # - a cart with the same product
        # - a cart with the same overnight period

        if (
            not self.rent_ok
            or not (cart := request.cart)
            or not (cart.rental_start_date and cart.rental_return_date)
        ):
            # Not a rental product, no cart, or no rentals in the current cart
            return True

        if cart.order_line.filtered('is_rental').product_id == self:
            # Only rental product in cart is the current product so we allow any period change
            return True

        best_pricing = self._get_best_pricing_rule(
            start_date=cart.rental_start_date,
            end_date=cart.rental_return_date,
            pricelist=request.pricelist,
            currency=request.website.currency_id,
        )
        pricing_recurrence = best_pricing.recurrence_id
        if not pricing_recurrence or not pricing_recurrence.overnight:
            # Not an overnight pricing: not an issue (worst case the customer is overpriced)
            return True

        website_tz = timezone(request.website.tz)
        pickup_time, return_time = pricing_recurrence.pickup_time, pricing_recurrence.return_time
        pickup_date, return_date = (
            cart.rental_start_date.astimezone(website_tz),
            cart.rental_return_date.astimezone(website_tz),
        )

        return (
            (pickup_date.hour + pickup_date.minute / 60) == pickup_time
            and (return_date.hour + return_date.minute / 60) == return_time
            and pickup_date.day != return_date.day
        )
