# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo.http import request


class AppointmentHrRecruitmentController(AppointmentController):

    def _get_extra_calendar_event_params(self, **kwargs):
        res = super()._get_extra_calendar_event_params(**kwargs)
        if applicant_code := kwargs.get('applicant_code'):
            applicant_sudo = request.env['hr.applicant'].sudo().search([
                ('interview_invite_code', '=', applicant_code)
            ], limit=1)
            if applicant_sudo:
                res['applicant_id'] = applicant_sudo.id
        return res
