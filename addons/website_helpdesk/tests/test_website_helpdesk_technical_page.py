from odoo.tests import tagged
from odoo.addons.website.tests.test_website_technical_page import TestWebsiteTechnicalPage


@tagged("post_install", "-at_install")
class TestWebsiteHelpdeskTechnicalPage(TestWebsiteTechnicalPage):

    def test_load_website_helpdesk_technical_pages(self):
        self._validate_routes(["/helpdesk"])
