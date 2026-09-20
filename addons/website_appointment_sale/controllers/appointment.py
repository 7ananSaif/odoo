# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request

from odoo.addons.appointment_account_payment.controllers.appointment import AppointmentAccountPayment
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.addons.portal.controllers.portal import CustomerPortal


class WebsiteAppointmentSale(AppointmentAccountPayment):

    def _redirect_to_payment(self, calendar_booking):
        """ Override: when using a payment step, we go through the eCommerce flow instead,
            and link the booking to the SOL as one can go through the flow several times and book
            several slots of the same appointment type """
        order_sudo = request.cart or request.website._create_cart()

        # Necessary to have a description matching the tz picked by partner.
        # See _prepare_order_line_values on sale.order model.
        tz = (request.session.get('timezone') or
              request.env.context.get('tz') or
              calendar_booking.appointment_type_id.appointment_tz)

        cart_values = order_sudo._cart_add(
            product_id=calendar_booking.appointment_type_id.product_id.id,
            quantity=calendar_booking.asked_capacity,
            calendar_booking_id=calendar_booking.id,
            calendar_booking_tz=tz
        )
        if cart_values['quantity'] == calendar_booking.asked_capacity:  # Booking successfully added to cart
            if order_sudo._is_anonymous_cart():
                partner_values = {
                    'name': calendar_booking.name,
                    'email': calendar_booking.partner_id.email,
                    'phone': calendar_booking.partner_id.phone,
                }
                booked_by_partner, feedback_dict = CustomerPortal()._create_or_update_address(
                    request.env['res.partner'].sudo(),
                    order_sudo=order_sudo,
                    verify_address_values=False,
                    **partner_values
                )
                if not feedback_dict.get('invalid_fields'):
                    order_sudo._update_address(booked_by_partner.id, ['partner_id'])
            return request.redirect("/shop/checkout?try_skip_step=true")

        # Slot not available. We remove booking and redirect to appointment.
        appointment_type = calendar_booking.appointment_type_id
        calendar_booking.sudo().unlink()
        error_state = 'failed-staff-user' if appointment_type.schedule_based_on == 'users' else 'failed-resource'
        return request.redirect('/appointment/%s?%s' % (appointment_type.id, keep_query('*', state=error_state)))
