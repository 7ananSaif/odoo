from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command, fields
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.addons.whatsapp.tests.common import WhatsAppCommon, MockOutgoingWhatsApp


class WhatsAppCalendar(WhatsAppCommon, MockOutgoingWhatsApp, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partners = cls.env['res.partner'].create([
            {'name': 'Test Partner 1', 'phone': '+91 12345 67891', 'country_id': cls.env.ref('base.in').id},
            {'name': 'Test Partner 2', 'phone': '+32455001122', 'country_id': cls.env.ref('base.be').id},
        ])

        cls.wa_template = cls.env['whatsapp.template'].create({
            'name': 'Test Whatsapp Calendar Template',
            'model_id': cls.env['ir.model']._get_id('calendar.attendee'),
            'body': 'This is body',
            'status': 'approved',
            'phone_field': 'phone',
            'wa_account_id': cls.whatsapp_account.id,
        })

        cls.calendar_alarm_wo_notify_responsible = cls.env['calendar.alarm'].create({
            'name': 'Whatsapp Alarm',
            'alarm_type': 'whatsapp',
            'wa_template_id': cls.wa_template.id,
            'interval': 'minutes',
            'duration': 10,
        })
        cls.calendar_alarm_w_notify_responsible = cls.calendar_alarm_wo_notify_responsible.copy({'notify_responsible': True})

    @freeze_time("2023-12-19 10:00:00")
    def test_whatsapp_alarm(self):
        """ Test that whatsapp alarm sends message(s) to suitable partner(s) based on the notify_responsible configuration. """
        now = fields.Datetime.now()
        # Ensure consistent phone number when demo data is missing
        self.env.ref('base.partner_admin').phone = '+1 555-555-5555'
        for calendar_event, last_call_minutes, expected_phone_numbers in [
            (
                # Calendar event with notify_responsible and with organizer
                {
                    'name': 'Test calendar event 1',
                    'start': now + relativedelta(minutes=3),
                    'stop': now + relativedelta(minutes=10),
                    'partner_ids': [Command.link(partner) for partner in self.partners.ids + [self.env.ref('base.partner_admin').id]],
                    'alarm_ids': [Command.link(self.calendar_alarm_w_notify_responsible.id)],
                    'user_id': self.env.ref('base.user_admin').id,
                },
                7,  # last call: 7 minutes before current time
                self.partners.mapped('phone') + [self.env.ref('base.partner_admin').phone],   # 3 messages sent: one to organizer, two to partners
            ), (
                # Calendar event without notify_responsible and with organizer
                {
                    'name': 'Test calendar event 2',
                    'start': now + relativedelta(minutes=6),
                    'stop': now + relativedelta(minutes=10),
                    'partner_ids': [Command.link(partner) for partner in self.partners.ids + [self.env.ref('base.partner_admin').id]],
                    'alarm_ids': [Command.link(self.calendar_alarm_wo_notify_responsible.id)],
                    'user_id': self.env.ref('base.user_admin').id,
                },
                4,  # last call: 4 minutes before current time
                self.partners.mapped('phone'),   # 2 messages sent: both to partners
            ), (
                # Calendar event without organizer
                {
                    'name': 'Test calendar event 3',
                    'start': now + relativedelta(minutes=9),
                    'stop': now + relativedelta(minutes=10),
                    'partner_ids': [Command.link(partner) for partner in self.partners.ids],
                    'alarm_ids': [Command.link(self.calendar_alarm_w_notify_responsible.id)],
                    'user_id': False,
                },
                1,  # last call: 1 minute before current time
                self.partners.mapped('phone'),  # 2 messages sent: both to partners
            )
        ]:
            with self.capture_triggers('calendar.ir_cron_scheduler_alarm') as capt:
                _event = self.env['calendar.event'].create(calendar_event)
            self.assertEqual(len(capt.records), 1)
            self.assertLessEqual(capt.records.call_at, now)

            with self.mockWhatsappGateway():
                self.env['calendar.alarm_manager'].with_context(lastcall=now - relativedelta(minutes=last_call_minutes))._send_reminder()
            self.assertEqual(self._new_wa_msg.mapped('mobile_number'), expected_phone_numbers)
