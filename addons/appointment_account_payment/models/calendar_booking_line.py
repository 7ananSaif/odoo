# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CalendarBookingLine(models.Model):
    _name = 'calendar.booking.line'
    _description = "Meeting User/Resource Booking"
    _order = "create_date DESC, id DESC"
    _rec_name = "calendar_booking_id"

    appointment_resource_id = fields.Many2one('appointment.resource', 'Resource', ondelete='cascade', readonly=True)
    appointment_user_id = fields.Many2one('res.users', 'Users', related="calendar_booking_id.staff_user_id")
    calendar_booking_id = fields.Many2one('calendar.booking', 'Meeting Booking', index=True, ondelete='cascade', required=True)
    capacity_reserved = fields.Integer('Capacity Reserved', default=1, readonly=True)
    capacity_used = fields.Integer('Capacity Used', readonly=True)
