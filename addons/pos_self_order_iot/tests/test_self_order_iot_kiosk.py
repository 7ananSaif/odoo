from odoo.fields import Command
import odoo.tests
from odoo.addons.iot.tests.common import IotCommonTest
from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@odoo.tests.tagged("post_install", "-at_install")
class TestSelfOrderIoTKiosk(IotCommonTest, SelfOrderCommonTest):
    def setUp(self):
        super().setUp()
        self.iot_websocket_messages = []
        self.pos_config.write({
            'self_ordering_mode': 'kiosk',
            'self_ordering_pay_after': 'each',
            'self_ordering_service_mode': 'counter',
            'payment_method_ids': [(4, self.bank_payment_method.id)],
            'available_preset_ids': [(5, 0)],
        })
        self.pos_config.default_preset_id.service_at = 'counter'

    def test_kiosk_receipt_printer(self):
        self.pos_config.write({
            'is_posbox': True,
            'iface_print_via_proxy': True,
            'iface_printer_id': self.iot_receipt_printer.id,
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()

        self.start_tour(self_route, "self_order_kiosk_iot_printer")
        self._check_ws_print_success()

    def test_kiosk_preparation_printer(self):
        self.env['pos.printer'].create({
            'name': 'IoT Preparation Printer',
            'printer_type': 'iot',
            'device_id': self.iot_receipt_printer.id,
            'product_categories_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })
        self.pos_config.write({
            'is_posbox': False,
            'printer_ids': [Command.set(self.env['pos.printer'].search([('printer_type', '=', 'iot')]).ids)],
        })
        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, "self_order_kiosk_iot_printer")
        self._check_ws_print_success()

    def _check_ws_print_success(self):
        """Check if websocket received the expected messages for printing via IoT Box."""
        self.assertEqual(
            len(self.iot_websocket_messages),
            3,
            (
                "`iot.channel.send_message` should be called exactly three times: "
                "webrtc offer, websocket action, then operation confirmation."
                "This time, we received %s" % [next(iter(message.keys())) for message in self.iot_websocket_messages]
            ),
        )
        self.assertIn(
            'webrtc_offer', self.iot_websocket_messages[0], "First ws message should be of type 'webrtc_offer'."
        )
        self.assertIn(
            'iot_action', self.iot_websocket_messages[1], "Second ws message should be of type 'iot_action'."
        )
        self.assertIn(
            'operation_confirmation',
            self.iot_websocket_messages[2],
            "Second ws message should be of type 'operation_confirmation'."
        )
