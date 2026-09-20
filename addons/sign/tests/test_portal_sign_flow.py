# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.base.tests.common import HttpCaseWithUserPortal
from odoo.tests import tagged
from .sign_request_common import SignRequestCommon


@tagged('post_install', '-at_install')
class TestPortalSignFlow(HttpCaseWithUserPortal, SignRequestCommon):

    def test_portal_sign_document(self):
        """Test for signing a document from the portal."""
        self.create_sign_request_1_role(self.partner_portal, self.env['res.partner'])
        self.start_tour("/", 'portal_sign_document', login="portal")

    def test_portal_download_signed_document(self):
        """Test for download a signed document using download button."""
        sign_request = self.create_sign_request_1_role(self.partner_portal, self.env['res.partner'])
        sign_request_item = {sign_request_item.role_id: sign_request_item for sign_request_item in sign_request.request_item_ids}
        sign_request_item_signer_1 = sign_request_item[self.role_signer_1]

        sign_request_item_signer_1.sudo().sign(self.single_signer_sign_values)
        self.start_tour("/", 'portal_download_signed_document', login="portal")
