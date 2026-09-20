from odoo.tests import common, tagged


@tagged("voip", "post_install", "-at_install")
class TestVoipMailActivity(common.TransactionCase):
    def test_voip_mail_activity_country_code_mixin(self):
        """Tests that "country_code_from_phone" is properly computed based on a phone field"""
        some_partner = self.env["res.partner"].create({"name": "Some partner", "phone": "+493023125513"})
        activity = some_partner.activity_schedule("mail.mail_activity_data_call")
        self.assertEqual(activity.phone_country_id.code.lower(), "de")
