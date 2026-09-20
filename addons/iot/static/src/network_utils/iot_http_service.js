import { registry } from "@web/core/registry";
import { post } from "@iot_base/network_utils/http";
import { uuid } from "@web/core/utils/strings";
import { IotWebsocket } from "@iot/network_utils/iot_websocket";
import { _t } from "@web/core/l10n/translation";
import { IotWebRtc } from "./iot_webrtc";

export const PRINTER_MESSAGES = {
    ERROR_FAILED: _t("Failed to initiate print"),
    ERROR_OFFLINE: _t("Printer is not ready"),
    ERROR_TIMEOUT: _t("Printing timed out"),
    ERROR_NO_PAPER: _t("Out of paper"),
    ERROR_UNREACHABLE: _t("Printer is unreachable"),
    ERROR_UNKNOWN: _t("Unknown printer error occurred"),
    WARNING_LOW_PAPER: _t("Paper is low"),
};

export const FDM_MESSAGES = {
    '000': _t("Blackbox is running and operational"),
    '001': _t("PIN accepted."),
    101: _t("Fiscal Data Module memory 90% full."),
    102: _t("Repeated request. This request was already handled by the fiscal data module."),
    103: _t("Operation wasn't saved on the blackbox"),
    199: _t("Unspecified warning."),
    201: _t("No Vat Signing Card or Vat Signing Card broken."),
    202: _t("Please activate the Vat Signing Card with PIN."),
    203: _t("Vat Signing Card blocked."),
    204: _t("Invalid PIN."),
    205: _t("Fiscal Data Module memory full."),
    206: _t("Unknown identifier."),
    207: _t("Invalid data in message sent to the blackbox."),
    208: _t("Fiscal Data Module not operational. Please restart the blackbox"),
    209: _t("Fiscal Data Module real time clock corrupt."),
    210: _t("Vat Signing Card not compatible with Fiscal Data Module."),
    299: _t("Unspecified error."),
    300: _t("Blackbox responded with invalid response. Please check the cable connection and the power supply, then retry. Restart if necessary"),
    301: _t("Blackbox did not respond to your request. This usually means it has disconnected. Please check its cable connection and its power supply. Restart if necessary."),
    426: _t("Blackbox driver update required. Please restart your IoT Box to update the blackbox driver."),
};

/**
 * Class to handle IoT actions
 * The class is used to send actions to IoT devices and handle fallbacks
 * in case the request fails: it will try to send the request using
 * HTTP POST method and then using the websocket.
 */
export class IotHttpService {
    longpollingFailedTimestamp = null;
    webRtcFailedTimestamp = null;
    connectionStatus = "webrtc"; // webrtc, longpolling, websocket, offline
    connectionTypes = [
        this._webRtc.bind(this),
        this._longpolling.bind(this),
        this._websocket.bind(this)
    ];
    cachedIotBoxes = {};

    constructor() {
        this.setup(...arguments);
    }

    /**
     * @param {import("services").ServiceFactories & { websocket: IotWebsocket } & { webRtc: IotWebRtc } }} services
     */
    setup({ iot_longpolling, websocket, webRtc, notification, orm }) {
        this.longpolling = iot_longpolling;
        this.websocket = websocket;
        this.webRtc = webRtc;
        this.notification = notification;
        this.orm = orm;
    }

    onFailure(_message, deviceIdentifier, _messageId) {
        this.notification.add(_t("Failed to reach the IoT Box for device: %s", deviceIdentifier), { type: "danger" });
    }

    cacheIotBoxRecords(boxes) {
        for (const box of boxes) {
            this.cachedIotBoxes[box.id] = { ip: box.ip, identifier: box.identifier, version: box.version };
        }
    }

    async getIotBoxData(iotBoxId) {
        const record = await this.orm.searchRead("iot.box", [["id", "=", iotBoxId]], ["id", "ip", "identifier", "version"]);
        if (!record) {
            throw new Error(`No IoT Box found`);
        }
        return record;
    }

    _ensureLongpollingEnabled() {
        if (
            this.longpollingFailedTimestamp &&
            Date.now() - this.longpollingFailedTimestamp < 5 * 60 * 1000
        ) {
            throw new Error("Longpolling is temporarily disabled due to a recent failure.");
        }
    }

    _ensureWebRtcEnabled() {
        if (
            this.webRtcFailedTimestamp &&
            Date.now() - this.webRtcFailedTimestamp < 20 * 60 * 1000
        ) {
            throw new Error("WebRTC is temporarily disabled due to a recent failure.");
        }
    }

    async _webRtc({ identifier, version, deviceIdentifier, data, messageId, onSuccess, onFailure, messageType }) {
        if (/\d{4}\.\d{2}\.\d{2}/.test(version)) {
            throw new Error("IoT box does not support WebRTC, skipping.");
        }
        this._ensureWebRtcEnabled();
        try {
            await this.webRtc.onMessage(identifier, deviceIdentifier, messageId, onSuccess, onFailure);
            if (data) {
                await this.webRtc.sendMessage(identifier, {
                    device_identifier: deviceIdentifier,
                    data,
                }, messageId, messageType);
            }
        } catch (error) {
            this.webRtcFailedTimestamp = Date.now();
            throw error;
        }
        this.connectionStatus = "webrtc";
    }

    async _longpolling({ ip, deviceIdentifier, data, messageId, onSuccess, onFailure }) {
        this._ensureLongpollingEnabled();
        try {
            this.longpolling.onMessage(ip, deviceIdentifier, onSuccess, onFailure, messageId);
            if (data) {
                const response =
                    await this.longpolling.sendMessage(ip, { device_identifier: deviceIdentifier, data }, messageId, true);
                if (response?.result === false) {
                    onFailure({status: "disconnected"}, deviceIdentifier, messageId);
                }
            }
        } catch (e) {
            this.longpollingFailedTimestamp = Date.now();
            throw e;
        }
        this.connectionStatus = "longpolling";
    }

    async _websocket({ identifier, deviceIdentifier, data, messageId, onSuccess, onFailure, messageType }) {
        const onFailureWithTimeout = (...args) => {
            onFailure(...args);
            this.connectionStatus = "offline";
        };
        this.websocket.onMessage(identifier, deviceIdentifier, onSuccess, onFailureWithTimeout, "operation_confirmation", messageId);
        if (data) {
            this.websocket.sendMessage(
                identifier,
                {
                    device_identifiers: [deviceIdentifier],
                    device_identifier: deviceIdentifier, // compatibility with v19.1+ IoT Boxes
                    ...data
                },
                messageId,
                messageType,
            );
        }
        this.connectionStatus = "websocket";
    }

    async _attemptFallbacks({ iotBoxId, deviceIdentifier, data, onFailure }) {
        if (!["number", "string"].includes(typeof iotBoxId)) {
            iotBoxId = iotBoxId[0]; // iotBoxId is the ``Many2one`` field, we need the actual ID
        }

        if (!this.cachedIotBoxes[iotBoxId]) {
            this.cacheIotBoxRecords(await this.getIotBoxData(iotBoxId))
        }
        const { ip, identifier, version } = this.cachedIotBoxes[iotBoxId];

        // if we target the box instead of a device, we want longpolling to handle action as messageType
        const messageType = deviceIdentifier === identifier ? data.action : undefined;
        const params = { ip, identifier, version, data, messageType, ...arguments[0] };

        for (const connectionType of this.connectionTypes) {
            try {
                return await connectionType(params);
            } catch (e) {
                console.debug("IoT Box action: attempted method failed, attempting another protocol.", e);
            }
        }

        // If all the connection types failed, run the onFailure callback and remove the cached IoT Box data
        delete this.cachedIotBoxes[iotBoxId];
        this.connectionStatus = "offline";
        onFailure({ status: "disconnected" }, deviceIdentifier);
    }

    /**
     * Listen for events on the IoT Box
     * @param iotBoxId IoT Box record ID
     * @param deviceIdentifier Identifier of the device connected to the IoT Box
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onSuccess Callback to run when a message is received
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onFailure Callback to run when the request fails
     * @param {string|null} messageId Unique identifier for the message (optional)
     * @returns {Promise<void>}
     */
    async onMessage(
        iotBoxId,
        deviceIdentifier,
        onSuccess = () => {},
        onFailure = (...args) => this.onFailure(...args),
        messageId = null,
    ) {
        // Attempt to listen for messages using the defined connection types
        await this._attemptFallbacks({
            iotBoxId,
            deviceIdentifier,
            messageId,
            onSuccess,
            onFailure,
        });
    }

    /**
     * Call for an action method on the IoT Box
     * @param iotBoxId IoT Box record ID
     * @param deviceIdentifier Identifier of the device connected to the IoT Box
     * @param data Data to send
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onSuccess Callback to run when a message is received
     * @param {(message: Record<string, unknown>, deviceId: string) => void} onFailure Callback to run when the request fails
     * @param {string|null} messageId Unique identifier for the message (optional)
     * @returns {Promise<void>}
     */
    async action(
        iotBoxId,
        deviceIdentifier,
        data,
        onSuccess = () => {},
        onFailure = (...args) => this.onFailure(...args),
        messageId = null,
    ) {
        messageId ??= uuid();

        if (!data) {
            data = {};
        }
        data.action_unique_id = messageId;

        await this._attemptFallbacks({
            iotBoxId,
            deviceIdentifier,
            data,
            messageId,
            onSuccess,
            onFailure,
        });
    }
}


export const iotHttpService = {
    dependencies: ["notification", "orm", "bus_service", "iot_longpolling", "lazy_session"],

    start(env, services) {
        const { iot_longpolling, bus_service } = services;
        const iotWebsocket = new IotWebsocket(services);
        const iotWebRtc = new IotWebRtc(bus_service, iotWebsocket);

        const webRtc = {
            sendMessage: iotWebRtc.sendMessage.bind(iotWebRtc),
            onMessage: iotWebRtc.onMessage.bind(iotWebRtc),
        };

        const longpolling = {
            sendMessage: iot_longpolling.sendMessage.bind(iot_longpolling),
            onMessage: iot_longpolling.onMessage.bind(iot_longpolling),
        };

        const websocket = {
            sendMessage: iotWebsocket.sendMessage.bind(iotWebsocket),
            onMessage: iotWebsocket.onMessage.bind(iotWebsocket),
        };

        const iot = new IotHttpService({ ...services, websocket: iotWebsocket, webRtc: iotWebRtc });
        const cacheIotBoxRecords = iot.cacheIotBoxRecords.bind(iot);
        const action = iot.action.bind(iot);
        const onMessage = iot.onMessage.bind(iot);

        // Expose only those functions to the environment
        // status is a getter to have a reactive value
        return {
            post, action, webRtc, longpolling, websocket, onMessage, cacheIotBoxRecords, get status() {
                return iot.connectionStatus;
            }
        };
    },
};

registry.category("services").add("iot_http", iotHttpService);
