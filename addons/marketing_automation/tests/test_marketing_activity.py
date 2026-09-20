from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.tests import Form


class TestMarketingActivity(MarketingAutomationCommon):

    def test_activity_summary(self):
        activity_form = Form(self.env['marketing.activity'])
        activity_form.name = "Test Activity"
        activity_form.interval_number = 3
        activity_form.interval_type = None
        self.assertEqual(activity_form.activity_summary, '')

        activity_form.interval_type = 'days'
        activity_form.validity_duration = True
        activity_form.validity_duration_number = 5
        activity_form.validity_duration_type = 'hours'
        self.assertIn("3 Days", activity_form.activity_summary)
        self.assertIn("5 Hours", activity_form.activity_summary)

        activity_form.validity_duration_type = None
        self.assertEqual(activity_form.activity_summary, '')
