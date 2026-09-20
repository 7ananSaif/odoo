import base64

from odoo import Command
from odoo.addons.l10n_br_edi_pos.tests.test_l10n_br_edi_pos import CommonPosBrEdiTest, TestL10nBREDIPOSCommon
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger


@tagged("post_install_l10n", "post_install", "-at_install")
class TestNfceDownload(CommonPosBrEdiTest, HttpCase, TestL10nBREDIPOSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sample_xml_content = b'<?xml version="1.0" encoding="UTF-8"?><nfce><infNFe>Sample NFCe XML</infNFe></nfce>'
        cls.sample_xml_content_2 = b'<?xml version="1.0" encoding="UTF-8"?><nfce><infNFe>Another NFCe XML</infNFe></nfce>'
        cls.pos_manager_user = cls._create_user("Test User", "test_user", cls.env.ref('point_of_sale.group_pos_manager').id)
        cls.unauthorized_user = cls._create_user("Unauthorized User", "unauthorized_user", cls.env.ref('base.group_user').id)

    @classmethod
    def _create_user(cls, name, login, group_ids):
        """Create and return a new user with specified name, login, and group IDs."""
        return cls.env['res.users'].create({
            'name': name,
            'login': login,
            'password': login,
            'group_ids': [Command.set([group_ids])]
        })

    def _create_test_order_with_attachment(self, order_name="Order/0001", xml_content=None, status="accepted", create_attachment=True):
        """Helper method to create a POS order with XML attachment"""
        if xml_content is None:
            xml_content = self.sample_xml_content
        order, _ = self.create_backend_pos_order({
            'order_data': {'name': order_name},
            'line_data': [{
                'qty': 1,
                'price_unit': 10.0,
                'product_id': self.product_screens.product_variant_id.id,
            }],
        })
        order.l10n_br_last_avatax_status = status
        if create_attachment:
            self.env['ir.attachment'].create({
                'name': f'{order_name}.xml',
                'res_model': 'pos.order',
                'res_id': order.id,
                'res_field': 'l10n_br_edi_xml_attachment_file',
                'datas': base64.b64encode(xml_content).decode(),
                'mimetype': 'application/xml',
            })
        return order

    def _assert_download_response(self, action, expected_status=200, expect_zip=True):
        """Helper method to assert the download response from an action."""
        response = self.url_open(url=action['url'], allow_redirects=False)
        self.assertEqual(response.status_code, expected_status)
        if expect_zip:
            self.assertRegex(response.headers.get('Content-Disposition'), r"NFC-e_XML_Files.zip")
        return response

    def test_download_with_unauthorized_user_fails(self):
        """Test that a user without POS Manager access cannot download NFC-e XML files"""
        order = self._create_test_order_with_attachment("Order/0003", status="accepted", create_attachment=True)
        self.authenticate('unauthorized_user', 'unauthorized_user')

        action = order._l10n_br_edi_action_download()
        with mute_logger('odoo.http'):
            response = self.url_open(url=action['url'], allow_redirects=False)
        self.assertEqual(response.status_code, 403)

    def test_download_order_without_attachment_fails(self):
        """Test that orders without XML attachment cannot be downloaded"""
        order = self._create_test_order_with_attachment("Order/0001", status="accepted", create_attachment=False)
        with self.assertRaisesRegex(UserError, "Oops! Some orders are not ready for XML download: Order/0001"):
            order._l10n_br_edi_action_download()

    def test_download_order_not_accepted_fails(self):
        """Test that orders with non-accepted status cannot be downloaded"""
        order = self._create_test_order_with_attachment("Order/0001", status="error", create_attachment=True)
        with self.assertRaisesRegex(UserError, "Oops! Some orders are not ready for XML download: Order/0001"):
            order._l10n_br_edi_action_download()

    def test_download_mixed_orders_fails(self):
        """Test that download fails when mixing valid and invalid orders"""
        valid_order = self._create_test_order_with_attachment("Order/0001", status="accepted", create_attachment=True)
        invalid_order = self._create_test_order_with_attachment("Order/0002", status="accepted", create_attachment=False)
        orders = valid_order + invalid_order
        with self.assertRaisesRegex(UserError, "Order/0002"):
            orders._l10n_br_edi_action_download()

    def test_download_mixed_status_orders_fails(self):
        """Test that download fails when orders have different statuses"""
        accepted_order = self._create_test_order_with_attachment("Order/0001", status="accepted", create_attachment=True)
        pending_order = self._create_test_order_with_attachment("Order/0002", status="error", create_attachment=True)
        orders = accepted_order + pending_order
        with self.assertRaisesRegex(UserError, "Order/0002"):
            orders._l10n_br_edi_action_download()

    def test_download_single_order(self):
        """Test download ZIP for a single valid NFCe order"""
        order = self._create_test_order_with_attachment("Order/0001")
        self.authenticate(self.env.user.login, self.env.user.login)
        self._assert_download_response(order._l10n_br_edi_action_download())

    def test_download_multiple_orders(self):
        """Test download ZIP for multiple valid NFCe orders"""
        order1 = self._create_test_order_with_attachment("Order/0001", self.sample_xml_content)
        order2 = self._create_test_order_with_attachment("Order/0002", self.sample_xml_content_2)
        orders = order1 + order2
        self.authenticate(self.env.user.login, self.env.user.login)
        self._assert_download_response(orders._l10n_br_edi_action_download())
