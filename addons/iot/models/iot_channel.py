import secrets

from odoo import api, models


class IotChannel(models.AbstractModel):
    _name = 'iot.channel'
    _description = "The Websocket IoT Channel"

    def get_iot_channel(self):
        """Get the IoT websocket channel name (unique for every company).

        :return: The IoT websocket channel used to send the message
        """
        ir_config_parameter = self.env['ir.config_parameter'].sudo()
        ws_channel = ir_config_parameter.get_param('iot.ws_channel')
        if not ws_channel:
            ws_channel = ir_config_parameter.set_param('iot.ws_channel', f'iot_channel-{secrets.token_hex(16)}')

        return ws_channel

    @api.model
    def send_message(self, message, message_type='iot_action'):
        """Send a message to a device via websocket.

        :param dict message: The message to send to the IoT Box
        :param str message_type: The type of the message (Default: call an action on a device)
        """
        self.env['bus.bus']._sendone(self.get_iot_channel(), message_type, message)
