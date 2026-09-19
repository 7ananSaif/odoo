# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers import main


class WebsiteSale(main.WebsiteSale):

    @http.route("/shop/ups_check_service_type", type='jsonrpc', auth="public", website=True, sitemap=False)
    def ups_check_service_type_is_available(self, **post):
        return request.env['sale.order'].sudo().check_ups_service_type(post)

    @http.route("/shop/property_ups_carrier_account/set", type='http', auth="public", website=True, sitemap=False)
    def set_property_ups_carrier_account(self, **post):
        order_sudo = request.cart

        # set ups bill my account data in sale order
        if order_sudo.carrier_id.ups_bill_my_account and post.get('property_ups_carrier_account'):
            # Update Quotation property_ups_carrier_account
            order_sudo.write({
                'partner_ups_carrier_account': post['property_ups_carrier_account'],
            })
        return request.redirect("/shop/checkout")

    @http.route("/shop/property_ups_carrier_account/unset", type='http', auth="public", website=True, sitemap=False)
    def reset_property_ups_carrier_account(self, **post):
        order_sudo = request.cart
        # remove ups bill my account data in sale order
        if order_sudo.partner_ups_carrier_account:
            order_sudo.write({
                'partner_ups_carrier_account': False,
            })
        return request.redirect("/shop/checkout")
