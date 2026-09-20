from odoo import http, fields
from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController
from werkzeug.exceptions import Unauthorized


class PosSelfOrderControllerIot(PosSelfOrderController):
    @http.route("/pos-self-order/iot-payment-cancelled/", auth="public", type="jsonrpc", website=True)
    def iot_payment_cancelled(self, access_token, order_id):
        pos_config = self._verify_pos_config(access_token)
        order = pos_config.env["pos.order"].search([("id", "=", order_id), ("config_id", "=", pos_config.id)])
        order._send_payment_result('fail')

    @http.route("/pos-self-order/iot-payment-success/", auth="public", type="jsonrpc", website=True)
    def iot_payment_success(self, access_token, order_id, payment_method_id, payment_info):
        pos_config = self._verify_pos_config(access_token)
        payment_method = pos_config.payment_method_ids.filtered(lambda p: p.id == payment_method_id)
        order = pos_config.env["pos.order"].search([("id", "=", order_id), ("config_id", "=", pos_config.id)])
        order.add_payment({
            "amount": order.amount_total,
            "payment_date": fields.Datetime.now(),
            "payment_method_id": payment_method.id,
            "card_type": payment_info["Card"],
            "transaction_id": str(payment_info["PaymentTransactionID"]),
            "payment_status": "Success",
            "ticket": payment_info["Ticket"],
            "pos_order_id": order.id
        })

        order.action_pos_order_paid()

        if order.config_id.self_ordering_mode == "kiosk":
            order._send_payment_result('Success')

    @http.route("/pos-self-order/get-iot-box-data/", auth="public", type="jsonrpc", website=True)
    def get_iot_box_data(self, access_token, iot_box_id):
        pos_config = self._verify_pos_config(access_token)
        iot_data = pos_config.env["iot.box"].sudo().browse(iot_box_id)
        if not iot_data:
            return {"error": "Self Order: No IoT Box found"}
        return iot_data.read(["ip", "identifier", "version"])

    @http.route("/pos-self-order/iot-box-websocket-channel/", auth="public", type="jsonrpc")
    def iot_box_websocket_channel(self, access_token, message=None, message_type="iot_action"):
        try:
            pos_config = self._verify_pos_config(access_token)
        except Unauthorized:
            # If pos is closed, we don't want a traceback, and we don't care
            # about sending messages to the iot box: we return an empty ws channel
            return ""
        iot_channel = pos_config.env['iot.channel']
        if message:
            iot_channel.send_message(message, message_type)

        return iot_channel.get_iot_channel()
