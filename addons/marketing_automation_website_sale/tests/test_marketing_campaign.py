# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon


@tagged('-at_install', 'post_install')
class TestCampaignTemplate(MarketingAutomationCommon):

    def test_anniversary_template(self):
        anniversary = self.campaign._get_marketing_template_anniversary()
        self.assertTrue(anniversary)
