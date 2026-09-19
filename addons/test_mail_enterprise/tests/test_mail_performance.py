from contextlib import contextmanager
from markupsafe import Markup
from unittest.mock import patch

from odoo.addons.mail_mobile.models import mail_thread
from odoo.addons.test_mail_full.tests.test_mail_performance import FullBaseMailPerformance
from odoo.tests.common import users, warmup
from odoo.tests import tagged
from odoo.tools import mute_logger


class EnterpriseBaseMailPerformance(FullBaseMailPerformance):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_ocn_for_partners(
            cls.user_admin.partner_id + cls.user_employee.partner_id +
            cls.user_follower_emp_email.partner_id +
            cls.user_follower_emp_inbox.partner_id +
            cls.user_follower_portal.partner_id +
            cls.partner_follower +
            cls.user_emp_inbox.partner_id +
            cls.user_emp_email.partner_id +
            cls.partner +
            cls.customers
        )

    def setUp(self):
        super().setUp()
        self._mock_ocn_iap_jsonrpc()

    @classmethod
    def _setup_ocn_for_partners(cls, partners, endpoint=None):
        """ Generate keys and tokens """
        cls.ocn_project_id = 'TestOcnProject'
        cls.env['ir.config_parameter'].sudo().set_param('odoo_ocn.project_id', cls.ocn_project_id)
        cls.env['ir.config_parameter'].sudo().set_param('mail_mobile.enable_ocn', True)
        cls.env['ir.config_parameter'].sudo().set_param('mail_mobile.disable_redirect_firebase_dynamic_link', False)

        for partner in partners:
            partner.ocn_token = f'OCN Token {partner.id}'

    @contextmanager
    def mock_ocn_iap_jsonrpc(self):
        with patch.object(mail_thread, 'iap_jsonrpc') as patched_iap_jsonrpc:
            self.ocn_iap_jsonrpc_mocked = patched_iap_jsonrpc
            yield

    @contextmanager
    def _mock_ocn_iap_jsonrpc(self):
        mock = self.mock_ocn_iap_jsonrpc()
        mock.__enter__()  # noqa: PLC2801
        self.addCleanup(lambda: mock.__exit__(None, None, None))


@tagged('mail_performance', 'post_install', '-at_install')
class TestMailPerformance(EnterpriseBaseMailPerformance):

    def test_assert_initial_values(self):
        """ Simply ensure some values through all tests """
        record_ticket = self.env['mail.test.ticket.mc'].browse(self.record_ticket_mc.ids)
        self.assertEqual(record_ticket.message_partner_ids,
                         self.user_follower_emp_email.partner_id + self.user_admin.partner_id + self.customers + self.user_follower_portal.partner_id)
        self.assertEqual(len(record_ticket.message_ids), 1)

    @mute_logger('odoo.tests', 'odoo.addons.mail.models.mail_mail', 'odoo.models.unlink')
    @users('employee')
    @warmup
    def test_message_post_w_followers(self):
        """ Aims to cover as much features of message_post as possible """
        record_ticket = self.env['mail.test.ticket.mc'].browse(self.record_ticket_mc.ids)
        attachments = self.env['ir.attachment'].create(self.test_attachments_vals)
        self.push_to_end_point_mocked.reset_mock()  # reset as executed twice
        self.ocn_iap_jsonrpc_mocked.reset_mock()  # reset as executed twice
        self.flush_tracking()

        with self.assertQueryCount(employee=159):  # tme: 153
            new_message = record_ticket.message_post(
                attachment_ids=attachments.ids,
                # atmention a user, as it generates a different chunk for ocn
                body=Markup('<p>Test Content<a href="/odoo" data-oe-id="%(partner_id)s" data-oe-model="res.partner">@user</a>') % {"partner_id": self.user_admin.partner_id.id},
                email_add_signature=True,
                mail_auto_delete=True,
                message_type='comment',
                subject='Test Subject',
                subtype_xmlid='mail.mt_comment',
                tracking_value_ids=self.tracking_values_ids,
            )

        self.assertEqual(
            new_message.notified_partner_ids,
            self.user_follower_emp_email.partner_id + self.user_admin.partner_id + self.customers + self.user_follower_portal.partner_id
        )
        self.assertEqual(self.push_to_end_point_mocked.call_count, 8, "Not sure why 8")
        self.assertEqual(self.ocn_iap_jsonrpc_mocked.call_count, 2, "One call for standard, one call for at mention")
