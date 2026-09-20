from odoo import tests

from odoo.addons.iot.tests.common import IotCommonTest


@tests.tagged('post_install', '-at_install')
class TestUi(IotCommonTest):
    iot_websocket_messages = []

    def test_iot_device_test_button(self):
        """Make sure we can use the websocket to test printers using the 'Test'
        button on the printer (iot.device) record."""
        self.start_tour("/odoo/iot", "iot_device_test_printer", login="admin")
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
