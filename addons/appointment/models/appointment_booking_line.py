# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AppointmentBookingLine(models.Model):
    _name = 'appointment.booking.line'
    _rec_name = "calendar_event_id"
    _description = "Appointment Booking Line"
    _order = "event_start desc, id desc"

    active = fields.Boolean(related="calendar_event_id.active")
    appointment_resource_id = fields.Many2one('appointment.resource', string="Appointment Resource",
        ondelete="cascade")
    appointment_user_id = fields.Many2one('res.users', string="Appointment User", related="calendar_event_id.user_id",
        readonly=False)
    appointment_type_id = fields.Many2one('appointment.type', related="calendar_event_id.appointment_type_id",
        precompute=True, store=True, readonly=True, ondelete="cascade", index=True)
    capacity_reserved = fields.Integer('Capacity Reserved', default=1, required=True,
        help="Capacity reserved by the user")
    capacity_used = fields.Integer('Capacity Used', compute="_compute_capacity_used", readonly=True,
        precompute=True, store=True, help="Capacity that will be used based on the capacity and user/resource selected")
    calendar_event_id = fields.Many2one('calendar.event', string="Booking", ondelete="cascade", required=True, index=True)
    event_start = fields.Datetime('Booking Start', related="calendar_event_id.start", readonly=True, store=True)
    event_stop = fields.Datetime('Booking End', related="calendar_event_id.stop", readonly=True, store=True)

    _check_capacity_reserved = models.Constraint(
        'CHECK(capacity_reserved >= 0)',
        "The capacity reserved should be positive.",
    )

    @api.constrains('appointment_resource_id', 'appointment_type_id', 'appointment_user_id')
    def _check_user_or_resource_set(self):
        for line in self:
            if ((line.appointment_type_id.schedule_based_on == 'users' and not line.appointment_user_id) or
                (line.appointment_type_id.schedule_based_on == 'resources' and not line.appointment_resource_id)):
                raise ValidationError(_('Booking line must have a user or resource set.'))

    @api.constrains('appointment_resource_id', 'appointment_type_id', 'appointment_user_id')
    def _check_user_or_resource_match_appointment_type(self):
        """Check appointment user/resource linked to the lines is indeed usable through the appointment type."""
        for appointment_type, lines in self.grouped('appointment_type_id').items():
            if appointment_type.schedule_based_on == 'users':
                non_compatible_users_and_resource = lines.appointment_user_id - appointment_type.staff_user_ids
            else:
                non_compatible_users_and_resource = lines.appointment_resource_id - appointment_type.resource_ids

            if non_compatible_users_and_resource:
                raise ValidationError(_('"%(name_list)s" cannot be used for "%(appointment_type_name)s"',
                                        appointment_type_name=appointment_type.name,
                                        name_list=', '.join(non_compatible_users_and_resource.mapped('name'))))

    @api.depends('appointment_resource_id.capacity', 'appointment_resource_id.shareable',
                 'appointment_type_id.manage_capacity', 'capacity_reserved')
    def _compute_capacity_used(self):
        self.capacity_used = 0
        for line in self:
            if line.capacity_reserved == 0:
                line.capacity_used = 0
            elif not line.appointment_type_id.manage_capacity:
                line.capacity_used = 1
            elif line.appointment_type_id.schedule_based_on == 'resources' and not line.appointment_resource_id.shareable:
                line.capacity_used = line.appointment_resource_id.capacity
            else:
                line.capacity_used = line.capacity_reserved
