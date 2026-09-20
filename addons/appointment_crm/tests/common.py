from datetime import datetime, timedelta

from odoo.addons.crm.tests.common import TestCrmCommon
from odoo.addons.mail.tests.common import mail_new_test_user


class TestAppointmentCrmCommon(TestCrmCommon):

    @classmethod
    def _create_appointment_type(cls, **kwargs):
        default = {
            "name": "Test Appointment",
            "appointment_duration": 1,
            "appointment_tz": "Europe/Brussels",
            "is_auto_assign": True,
            "max_schedule_days": 15,
            "min_cancellation_hours": 1,
            "min_schedule_hours": 1,
        }
        return cls.env['appointment.type'].create(dict(default, **kwargs))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.appointment_type_nocreate = cls._create_appointment_type(name="No Create")
        cls.user_employee = mail_new_test_user(
            cls.env, login='user_employee',
            name='Eglantine Employee', email='eglantine.employee@test.example.com',
            tz='Europe/Brussels', notification_type='inbox',
            company_id=cls.env.ref("base.main_company").id,
            groups='base.group_user',
        )
        # Used to test the staff user forcing during the run of appointment_crm_forced_staff_user_tour.
        cls.user_sales_leads_2 = mail_new_test_user(
            cls.env, login='user_sales_leads_2',
            name='Marc Sales Leads', email='crm_leads_2@test.example.com',
        )
        cls.appointment_type_create = cls._create_appointment_type(
            name="Create",
            lead_create=True,
            staff_user_ids=cls.user_sales_leads + cls.user_sales_leads_2,
            is_published=True
        )
        cls.appointment_type_resource_time_create = cls._create_appointment_type(
            name="Resource Time Appointment",
            lead_create=True,
            staff_user_ids=cls.user_sales_leads,
            is_auto_assign=False,
            is_date_first=False,
            is_published=True
        )

    def _prepare_event_value(self, appointment_type, user, contact, **kwargs):
        partner_ids = (user.partner_id | contact).ids
        default = {
            'name': '%s with %s' % (appointment_type.name, contact.name),
            'start': datetime.now(),
            'start_date': datetime.now(),
            'stop': datetime.now() + timedelta(hours=1),
            'allday': False,
            'duration': appointment_type.appointment_duration,
            'location': appointment_type.location,
            'partner_ids': [(4, pid, False) for pid in partner_ids],
            'appointment_type_id': appointment_type.id,
            'user_id': user.id,
        }
        return dict(default, **kwargs)

    def _create_meetings_from_appointment_type(self, appointment_type, user, contact, **kwargs):
        return self.env['calendar.event'].create(self._prepare_event_value(appointment_type, user, contact, **kwargs))
