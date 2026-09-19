from freezegun import freeze_time

from odoo.tests import Command, tagged, users
from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.addons.account_followup.tests.test_account_followup import TestAccountFollowupReports


@tagged('post_install', '-at_install')
class TestWhatsAppFollowup(WhatsAppCommon, TestAccountFollowupReports):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.phone = '+32499123456'
        cls.wa_template = cls.env['whatsapp.template'].with_user(cls.user_admin).create({
            'body': 'WhatsApp Followup {{1}}',
            'name': 'WhatsApp Followup test template',
            'status': 'approved',
            'wa_account_id': cls.whatsapp_account.id,
            'variable_ids': [
                Command.create({'name': "{{1}}", 'line_type': "body", 'field_type': 'user_name'}),
            ],
        })

    def create_followup(self, delay):
        followup = super().create_followup(delay)
        followup.send_whatsapp = True
        followup.whatsapp_template_id = self.wa_template
        return followup

    def test_whatsapp_followup_cron(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        followup_10 = self.create_followup(delay=10)
        followup_10.auto_execute = True

        self.create_invoice('2022-01-01')
        with (
            freeze_time('2022-01-11'),
            self.mockWhatsappGateway(),
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            cron.method_direct_trigger()
            self.assertWAMessageFromRecord(
                self.partner_a,
                fields_values={
                    'body': '<p>WhatsApp Followup OdooBot</p>',
                },
            )

    @users('admin')
    def test_whatsapp_followup_manual(self):
        def _run_wkhtmltopdf(*args, **kwargs):
            return bytes("0", "utf-8")
        self.patch(self.env.registry['ir.actions.report'], "_run_wkhtmltopdf", _run_wkhtmltopdf)

        reminder = self.env['account_followup.manual_reminder'].with_context(
            active_model='res.partner',
            active_ids=self.partner_a.ids,
        ).create({
            'print': False,
            'wa_template_id': self.wa_template.id,
            'whatsapp': True,
        })
        with self.mockWhatsappGateway():
            reminder.process_followup()
            self.assertWAMessageFromRecord(
                self.partner_a,
                fields_values={
                    'body': '<p>WhatsApp Followup Mitchell Admin</p>',
                },
            )

    @users('admin')
    def test_composer_raise_no_template_error(self):
        """
        The expected behavior is as follows:-
            In the presence of whatsapp templates
                whatsapp.composer should open error-free
                account_followup.manual_reminder should open error-free
            In the absence of whatsapp templates
                whatsapp.composer should throw an error
                account_followup.manual_reminder should open error-free
        """
        def open_wa_composer():
            self.env['whatsapp.composer'].with_context({
                'active_model': 'res.partner',
                'active_ids': self.partner_a.ids,
            }).create({})

        def open_followup_manual_reminder():
            self.env['account_followup.manual_reminder'].with_context(
                active_model='res.partner',
                active_ids=self.partner_a.ids,
            ).create({})

        open_wa_composer()
        open_followup_manual_reminder()

        # delete all whatsapp templates
        self.env['whatsapp.template'].with_user(self.user_admin).search([]).unlink()

        self.assertRaises(Exception, open_wa_composer)
        open_followup_manual_reminder()
