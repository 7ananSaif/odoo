# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.whatsapp.tests.common import MockIncomingWhatsApp, WhatsAppCommon
from odoo.addons.whatsapp.tools.whatsapp_api import DEFAULT_ENDPOINT, WhatsAppApi
from odoo.tests import tagged


@tagged('wa_message')
class WhatsAppAPI(WhatsAppCommon, MockIncomingWhatsApp):

    def test_receive_attachment_with_debug_requests(self):
        """Ensure attachment fetch requests are logged properly when debug logs are enabled."""
        doc_id = 'test_doc_id'
        doc_info_url = f'{DEFAULT_ENDPOINT}/{doc_id}'
        doc_bin_url = 'https://doc.getyadoc.lan'
        doc_bin_content = b'\x00\x01\x02Hello\x00World'
        doc_info_content = {
            "url": doc_bin_url,
            "mime_type": "image/jpeg",
            "sha256": "dummysha"
        }
        response_map = {
            doc_info_url: {
                'content': doc_info_content,
                'content_type': 'application/json',
            },
            doc_bin_url: {
                'content': doc_bin_content,
                'content_type': 'application/octet-stream',
            }
        }

        self.whatsapp_account.action_debug()
        with self.mockWhatsappHTTPResponse(response_map):
            response_val = WhatsAppApi(self.whatsapp_account)._get_whatsapp_document(doc_id)

        self.assertEqual(response_val, doc_bin_content)
        self.assertEqual(len(self._wa_http_requests), 2)

        doc_info_log_message = (
            "URL: https://graph.facebook.com/v23.0/test_doc_id\n"
            "Status Code: 200\n"
            f"Response Text: {self._wa_http_requests[0]['response'].content.decode()}"
        )
        doc_bin_response_repr = (
            f"[Binary Content]\n"
            f"Content-Type: application/octet-stream\n"
            f"Size: {len(doc_bin_content)} bytes\n"
        )
        doc_bin_log_message = (
            f"URL: {doc_bin_url}\n"
            f"Status Code: 200\n"
            f"Response Text: {doc_bin_response_repr}"
        )
        doc_bin_log, doc_info_log = self.env['ir.logging'].search([
            ('name', '=', 'WA Response'),
            ('path', 'like', f'whatsapp.account,id={self.whatsapp_account.id},name={self.whatsapp_account.name}'),
        ], limit=2)
        self.assertEqual(doc_info_log.message, doc_info_log_message)
        self.assertEqual(doc_bin_log.message, doc_bin_log_message)
