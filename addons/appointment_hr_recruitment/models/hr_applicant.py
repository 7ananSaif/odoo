# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models
from odoo.http import request

from odoo.addons.appointment.controllers.calendar_view import AppointmentCalendarView


class Applicant(models.Model):
    _inherit = "hr.applicant"

    interview_invite_code = fields.Char(readonly=True, copy=False, store=True, precompute=True, compute='_compute_interview_invite_code')

    def _compute_interview_invite_code(self):
        for app in self.filtered(lambda app: not app.interview_invite_code):
            app.interview_invite_code = uuid.uuid4().hex[:16]

    def action_create_meeting(self):
        res = super().action_create_meeting()
        if self.interview_invite_code:
            res['context']['applicant_code'] = self.interview_invite_code
        return res

    def _get_interview_invite_url(self):
        self.ensure_one()
        if not request:
            return ''

        return AppointmentCalendarView._appointment_type_search_create_anytime(
            context={**self.env.context, 'applicant_code': self.interview_invite_code},
            user=self.user_id,
        )['invite_url']
