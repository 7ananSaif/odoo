# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.http import request, route

from odoo.addons.website_sale.controllers.cart import Cart as WebsiteSaleCart


class Cart(WebsiteSaleCart):

    @route(
        '/shop/cart/update_renting',
        type='jsonrpc',
        auth='public',
        methods=['POST'],
        website=True
    )
    def update_cart_renting(self, start_date=None, end_date=None):
        """ Route to check the cart availability when changing the dates on the cart. """
        try:
            start_date = fields.Datetime.to_datetime(start_date)
            end_date = fields.Datetime.to_datetime(end_date)
        except ValueError:
            start_date = end_date = None
        if not (start_date and end_date and (order_sudo := request.cart)):
            return {}
        order_sudo._cart_update_renting_period(start_date, end_date)

        values = {
            'cart_quantity': order_sudo.cart_quantity,
            'cart_ready': order_sudo._is_cart_ready(),
        }
        values['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template(
            'website_sale.cart_lines', {
                'website_sale_order': order_sudo,
                'date': fields.Date.today(),
                'suggested_products': order_sudo._cart_accessories(),
            }
        )
        values['website_sale.total'] = request.env['ir.ui.view']._render_template(
            'website_sale.total', {
                'website_sale_order': order_sudo,
            }
        )
        return {
            'start_date': order_sudo.rental_start_date,
            'end_date': order_sudo.rental_return_date,
            'values': values,
        }

    @route()
    def add_to_cart(self, *args, start_date=None, end_date=None, **kwargs):
        """ Override to parse to datetime optional pickup and return dates. """
        start_date = fields.Datetime.to_datetime(start_date)
        end_date = fields.Datetime.to_datetime(end_date)
        return super().add_to_cart(
            *args, start_date=start_date, end_date=end_date, **kwargs
        )
