import { patch } from "@web/core/utils/patch";
import { IoTLongpolling } from "@iot_base/network_utils/longpolling";
import { uuid } from "@web/core/utils/strings";

patch(IoTLongpolling.prototype, {
    /**
     * Send a message to the IoT Box (action route)
     * @param iotBoxIp IP Address of the IoT Box
     * @param message Data to send to the device
     * @param messageId Unique identifier for the message
     * @param fallback If longpolling has a fallback option (e.g. websocket), do not display errors to the user
     * @returns {Promise<*>} response of the request (response.result tells if the device is connected or not)
     */
    async sendMessage(iotBoxIp, message, messageId = null, fallback = false) {
        messageId ??= uuid();
        return this._rpcIoT(iotBoxIp, '/iot_drivers/action', { session_id: messageId, ...message }, undefined, fallback);
    },

    /**
     * Listen for messages from the IoT Box (polling the IoT Box)
     * @param iotBoxIp IP Address of the IoT Box
     * @param iotDeviceIdentifier Identifier of the device connected to the IoT Box
     * @param onSuccess Callback to run when a successful response is received (can return ``message``, ``deviceIdentifier``, and ``messageId``)
     * @param onFailure Callback to run when the request fails (can return ``deviceIdentifier`` and ``messageId``)
     * @param requestId The request ID to listen for (optional)
     */
    onMessage(
        iotBoxIp,
        iotDeviceIdentifier,
        onSuccess = (_message, _deviceIdentifier, _messageId) => {},
        onFailure = (_message, _deviceIdentifier, _messageId) => {},
        requestId = null
    ) {
        const listenerCallback = (message) => {
            if (requestId && message.owner !== requestId) {
                return;
            }
            this.removeListener(iotBoxIp, iotDeviceIdentifier, requestId);
            if (message.status === "success" || message.status?.status === "connected") { // 'connected' is the serial driver success status
                onSuccess(message, iotDeviceIdentifier, requestId);
            } else {
                onFailure(message, iotDeviceIdentifier, requestId);
            }
        }
        return this.addListener(iotBoxIp, [ iotDeviceIdentifier ], requestId, listenerCallback, true);
    },
});
