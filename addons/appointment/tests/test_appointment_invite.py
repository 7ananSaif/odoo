# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.tests import Form, users


class AppointmentInviteTest(AppointmentCommon):

    def test_gc_appointment_invite(self):
        """ Remove invitations > 6 months old, with latest end of linked meeting > 6 months old """
        appt_invite = self.env['appointment.invite'].create({
            'appointment_type_ids': [(4, self.apt_type_bxls_2days.id)],
            'create_date': self.reference_now - relativedelta(months=8),
        })
        meeting_1, meeting_2 = self._create_meetings(
            self.staff_user_bxls,
            [(self.reference_now - relativedelta(months=5, hours=1),
              self.reference_now - relativedelta(months=5),
              False),
             (self.reference_now - relativedelta(months=7, hours=1),
              self.reference_now - relativedelta(months=7),
              False)]
        )
        (meeting_1 | meeting_2).appointment_invite_id = appt_invite.id

        with freeze_time(self.reference_now):
            self.env['appointment.invite']._gc_appointment_invite()
        self.assertTrue(appt_invite.exists())

        # Remove the most recent meeting. The one left is > 6 months old and should be removed by the GC.
        meeting_1.unlink()
        with freeze_time(self.reference_now):
            self.env['appointment.invite']._gc_appointment_invite()
        self.assertFalse(appt_invite.exists())

    @users('apt_manager')
    def test_short_code_genertation(self):
        """
        Case 1: Create appointment name based short_code when no link exist for the same appointment given that
                short_code does not exist for any invites.

        Case 2: Retrieve the existing short_code based on the given configuration else generate random short_code.

        Case 3: Generate random short_code if the user changes the given configuration (for already fetched short_code).

        Case 4: Allow to alter the already fetched short_code and save it.
        """
        apt_users = self.apt_manager + self.staff_users
        appointment_types = self.env['appointment.type'].create([{
            'name': f'Test Users {i}',
            'schedule_based_on': 'users',
            'staff_user_ids': apt_users.ids,
        } for i in range(0, 2)])

        AppointmentInvite1 = self.env['appointment.invite'].with_context(default_appointment_type_ids=[appointment_types[0].id])
        AppointmentInvite2 = self.env['appointment.invite'].with_context(default_appointment_type_ids=[appointment_types[1].id])
        # Case 1
        with Form(AppointmentInvite1) as appointment_invite:
            self.assertEqual(
                appointment_invite.short_code,
                'test-users-0',
                'Appointment name based short_code should be generated',
            )
            # manually change short code, important for next test
            appointment_invite.short_code = 'code-to-reuse'

        # Case 2(i)
        appointment_invite_reuse = Form(AppointmentInvite1)
        self.assertEqual(appointment_invite_reuse.short_code, 'code-to-reuse', 'The existing short_code should be retrieved')

        # Case 2(ii)
        with Form(AppointmentInvite2) as appointment_invite_other_config:
            appointment_invite_other_config.resources_choice = 'all_assigned_resources'
            self.assertEqual(appointment_invite_other_config.short_code, 'test-users-1')

        appointment_invite_different_config = Form(AppointmentInvite2)
        self.assertNotEqual(
            appointment_invite_different_config.short_code,
            'test-users-1',
            'The random short_code should be generated',
        )

        # Case 3
        appointment_invite_change_config = Form(AppointmentInvite1)
        self.assertEqual(appointment_invite_change_config.short_code, 'code-to-reuse')
        appointment_invite_change_config.resources_choice = 'all_assigned_resources'
        self.assertNotEqual(
            appointment_invite_change_config.short_code,
            'code-to-reuse',
            'The random short_code should be generated when config changes',
        )

        # Case 4
        with Form(AppointmentInvite1) as appointment_invite_change_code:
            appointment_invite_change_code.short_code = 'custom-code'
        self.assertEqual(appointment_invite_change_code.short_code, 'custom-code', 'A new share link should be created')
