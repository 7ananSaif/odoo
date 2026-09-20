# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.tests import tagged, HttpCase


@tagged("multi_company")
class WhatsAppMultiCompany(WhatsAppCommon, HttpCase):
    def test_read_whatsapp_channel_in_multi_company(self):
        wa_account_company_c3 = self.env["whatsapp.account"].create(
            {
                "account_uid": "mario",
                "app_secret": "1234567890mario",
                "app_uid": "contact_mario",
                "name": "Mario Account",
                "notify_user_ids": [(4, self.user_employee_c2.id)],
                "phone_uid": "88888888",
                "token": "event_mail_is_great_",
                "allowed_company_ids": self.company_3.ids,
            },
        )
        channel_company_c3 = self.env["discuss.channel"].create(
            {
                "channel_partner_ids": [(4, self.user_employee_c2.partner_id.id)],
                "channel_type": "whatsapp",
                "name": "Dummy WA Channel",
                "wa_account_id": wa_account_company_c3.id,
                "whatsapp_number": "911234567891",
                "whatsapp_partner_id": self.whatsapp_customer.id,
            }
        )
        self.assertFalse(
            wa_account_company_c3.with_user(self.user_employee_c2).has_access("read")
        )
        self.authenticate(self.user_employee_c2.login, self.user_employee_c2.login)
        data = self.make_jsonrpc_request(
            "/mail/data",
            {
                "fetch_params": [
                    ["discuss.channel", [channel_company_c3.id]],
                    "init_messaging",
                ],
            },
        )
        self.assertEqual(
            data["whatsapp.account"][0]["name"],
            "Mario Account",
        )
