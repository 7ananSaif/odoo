# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time
from datetime import datetime

from odoo.tests import HttpCase, tagged, users


@tagged('post_install', '-at_install')
class AppointmentHrRecruitmentTest(HttpCase):

    @users('admin')
    def test_tour_default_opportunity_propagation(self):
        """ Test that the applicant is correctly propagated to the appointment invitation created """
        with freeze_time(datetime(year=2025, month=2, day=12, hour=17)):
            self.env.user.tz = "Europe/Brussels"
            dep_rd = self.env['hr.department'].create({
                'name': 'Research & Development',
            })
            job_developer = self.env['hr.job'].create({
                'name': 'Test Job',
                'department_id': dep_rd.id,
                'no_of_recruitment': 5,
            })
            applicant = self.env['hr.applicant'].sudo().create({
                'partner_name': 'Test Applicant',
                'job_id': job_developer.id,
            })
            appointment_type = self.env['appointment.type'].create({'name': "Test AppointmentHrRecruitment"})
            self.start_tour('/odoo', 'appointment_hr_recruitment_tour', login='admin')
            calendar_event = self.env['calendar.event'].search([('applicant_id', '=', applicant.id)])
            self.assertIn('Ana Tourelle', calendar_event.name)
