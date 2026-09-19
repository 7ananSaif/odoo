import { uuid } from "@web/core/utils/strings";

/**
 * Class to handle Websocket connections
 */
export class IotWebsocket {
    constructor() {
        this.setup(...arguments);
    }

    async setup({ bus_service, orm, lazy_session }) {
        this.busService = bus_service;
        this.orm = orm;
        if (lazy_session) {
            lazy_session.getValue("iot_channel", (iotChannel) => {
                this.iotChannel = iotChannel;
            });
        } else {
            this.iotChannel = await this.orm.call("iot.channel", "get_iot_channel", [0]);
        }
    }

    /**
     * Send a message to the IoT Box
     * @param iotBoxIdentifier Identifier of the IoT Box
     * @param message Data to send to the device
     * @param messageId Unique identifier for the message (optional)
     * @param messageType Type of message to send (optional)
     * @returns {Promise<*>} The message ID
     */
    async sendMessage(iotBoxIdentifier, message, messageId = null, messageType = 'iot_action') {
        messageId ??= uuid();

        await this.orm.call("iot.channel", "send_message", [
            {
                iot_identifiers: [iotBoxIdentifier],
                iot_identifier: iotBoxIdentifier, // compatibility with v19.1+ IoT Boxes
                session_id: messageId,
                ...message
            },
            messageType
        ]);

        return messageId;
    }

    /**
     * Add a listener for events/messages coming from the IoT Box.
     * This method allows defining callbacks for success and failure cases.
     * @param iotBoxIdentifier Identifier of the IoT Box
     * @param deviceIdentifier Identifier of the device connected to the IoT Box
     * @param onSuccess Callback to run when a message is received (can return ``message``, ``deviceIdentifier``, and ``messageId``)
     * @param onFailure Callback to run when the request fails (can return ``deviceIdentifier`` and ``messageId``)
     * @param messageType The type of message to listen for (optional)
     * @param sessionId The session ID to listen for (optional)
     */
    onMessage(
        iotBoxIdentifier,
        deviceIdentifier,
        onSuccess = (_message, _deviceIdentifier, _messageId) => {},
        onFailure = (_message, _deviceIdentifier, _messageId) => {},
        messageType = 'operation_confirmation',
        sessionId = null,
    ) {
        if (!this.iotChannel) {
            console.error("No IoT Channel found");
            return;
        }
        const timeoutId = setTimeout(() => {
            console.debug("Websocket timeout for", iotBoxIdentifier, deviceIdentifier, sessionId);
            onFailure({
                status: "timeout",
                message: "Timeout waiting for IoT Box response, please try again.",
            }, deviceIdentifier, sessionId);
            this.busService.unsubscribe(messageType, messageCallback);
        }, 6000); // error callback if the listener is not called within 6 seconds

        const messageCallback = (event) => {
            const { session_id, iot_box_identifier, device_identifier, message } = event;
            if (
                iot_box_identifier !== iotBoxIdentifier ||
                device_identifier !== deviceIdentifier ||
                (sessionId && session_id !== sessionId)) {
                return;
            }

            const callback = message.status === "success" || message.status?.status === "connected" ? onSuccess : onFailure;
            callback(message);
            clearTimeout(timeoutId);
            this.busService.unsubscribe(messageType, messageCallback);
        }

        this.busService.addChannel(this.iotChannel);
        this.busService.subscribe(messageType, messageCallback);
    }
}
