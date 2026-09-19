import json
from odoo.tests import HttpCase
from unittest.mock import patch

from odoo.addons.iot.models.iot_channel import IotChannel


class IotCommonTest(HttpCase):
    iot_websocket_messages = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop_iot_box = cls.env['iot.box'].sudo().create({
            'name': 'Shop',
            'identifier': 'test_iot_box',
            'ip': '10.10.10.10',
            'version': '25.07',
        })

        cls.iot_receipt_printer = cls.env['iot.device'].sudo().create({
            'name': 'Receipt Printer',
            'identifier': 'printer_identifier',
            'iot_id': cls.shop_iot_box.id,
            'type': 'printer',
            'subtype': 'receipt_printer',
            'connection': 'network',
            'connected_status': 'connected',
        })

    def setUp(self):
        super().setUp()
        original_send_message = IotChannel.send_message

        def mock_send_message(iot_channel_record, message, message_type='iot_action'):
            self.iot_websocket_messages.append({message_type: message})
            if message_type == 'iot_action':
                # call the websocket response controller to simulate the response from the IoT Box
                return self.url_open(
                    '/iot/box/send_websocket',
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps({
                        'params': {
                            'session_id': message['session_id'],
                            'iot_box_identifier': message['iot_identifiers'][0],
                            'device_identifier': message['device_identifiers'][0],
                            'status': 'success',
                        },
                    }),
                )
            return original_send_message(iot_channel_record, message, message_type)

        def mock_get_iot_channel(_iot_channel_record):
            return "mock_iot_channel"

        mock_get_iot_channel._api_model = True
        mock_send_message._api_model = True

        send_message_patcher = patch.object(IotChannel, 'send_message', mock_send_message)
        channel_patcher = patch.object(IotChannel, 'get_iot_channel', mock_get_iot_channel)
        self.addCleanup(send_message_patcher.stop)
        self.addCleanup(channel_patcher.stop)
        send_message_patcher.start()
        channel_patcher.start()
