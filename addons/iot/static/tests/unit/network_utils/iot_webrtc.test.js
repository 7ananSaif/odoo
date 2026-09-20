import { IotWebRtc } from "@iot/network_utils/iot_webrtc";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import {
    defineModels,
    makeMockEnv,
    models,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { EventBus } from "@odoo/owl";

class IotChannel extends models.Model {
    get_iot_channel() {
        return "mockChannel";
    }
}

defineModels({ IotChannel });

class MockRtcDataChannel extends EventTarget {
    constructor(id) {
        super();
        this.id = id;
        this.readyState = "open";
        this._messagesSent = [];
    }

    send(message) {
        this._messagesSent.push(message);
    }

    close() {}
}

class MockRtcPeerConnection extends EventTarget {
    static _instances = 0;

    constructor() {
        super();
        MockRtcPeerConnection._instances += 1;
    }

    get sctp() {
        return { maxMessageSize: 100 };
    }

    createDataChannel(id) {
        return new MockRtcDataChannel(id);
    }

    createOffer() {
        this.signalingState = "have-local-offer";
        return "mockOffer";
    }

    setLocalDescription(description) {
        this.localDescription = description;
        return;
    }

    setRemoteDescription(description) {
        this.remoteDescription = description;
        this.connectionState = "connected";
        return;
    }

    close() {}
}

const websocketMessages = [];

const setupWebRtc = () => {
    const bus = new EventBus();
    const busCallbacks = new Map();
    const mockBusService = {
        addChannel: () => {},
        subscribe: (type, callback) => {
            busCallbacks.set(callback, (event) => callback(event.detail));
            bus.addEventListener(type, busCallbacks.get(callback));
        },
        unsubscribe: (type, callback) => bus.removeEventListener(type, busCallbacks.get(callback)),
        trigger: bus.trigger.bind(bus),
    };
    const mockWebsocket = {
        iotChannel: "mockChannel",
        sendMessage: (iotIdentifier, message, messageId, messageType) => {
            websocketMessages.push({ iotIdentifier, message, messageId, messageType });
        },
    };
    MockRtcPeerConnection._instances = 0;
    return { webRtc: new IotWebRtc(mockBusService, mockWebsocket), bus };
};

const setupWebRtcWithConnection = async (identifier) => {
    const { webRtc, bus } = setupWebRtc();
    await webRtc.openConnection(identifier);
    bus.trigger("webrtc_answer", { iot_box_identifier: identifier, answer: "mockAnswer" });

    return { webRtc, bus };
};

beforeEach(async () => {
    await makeMockEnv();
    websocketMessages.splice(0, websocketMessages.length);

    patchWithCleanup(window, {
        RTCPeerConnection: MockRtcPeerConnection,
    });
});

describe("opening connection", () => {
    test("sends webrtc offer via the websocket", async () => {
        const { webRtc } = setupWebRtc();

        await webRtc.openConnection("iot");

        expect(websocketMessages).toHaveLength(1);
        expect(websocketMessages[0].messageType).toBe("webrtc_offer");
        expect(websocketMessages[0].message).toEqual({ offer: "mockOffer" });
    });

    test("saves connection to connections dict", async () => {
        const { webRtc } = setupWebRtc();

        await webRtc.openConnection("iot");

        expect(webRtc.connections["iot"]).toBeOfType("object");
        expect(webRtc.connections["iot"].id).toBeOfType("string");
        expect(webRtc.connections["iot"].connection).toBeInstanceOf(MockRtcPeerConnection);
        expect(webRtc.connections["iot"].channel).toBeInstanceOf(MockRtcDataChannel);
    });

    test("sets local offer", async () => {
        const { webRtc } = setupWebRtc();

        await webRtc.openConnection("iot");

        expect(webRtc.connections["iot"].connection).toBeInstanceOf(MockRtcPeerConnection);
        expect(webRtc.connections["iot"].connection.localDescription).toBe("mockOffer");
    });

    test("sets remote offer received via bus", async () => {
        const { webRtc, bus } = setupWebRtc();

        await webRtc.openConnection("iot");
        bus.trigger("webrtc_answer", { iot_box_identifier: "iot", answer: "mockAnswer" });

        expect(webRtc.connections["iot"].connection.remoteDescription).toBe("mockAnswer");
    });

    test("only opens the connection once", async () => {
        const { webRtc } = setupWebRtc();

        const openConnectionPromise1 = webRtc.openConnection("iot");
        const openConnectionPromise2 = webRtc.openConnection("iot");
        await Promise.all([openConnectionPromise1, openConnectionPromise2]);

        expect(MockRtcPeerConnection._instances).toBe(1);
    });

    test("opens separate connections per IoT box", async () => {
        const { webRtc, bus } = setupWebRtc();

        const openConnectionPromise1 = webRtc.openConnection("iot");
        const openConnectionPromise2 = webRtc.openConnection("iot2");
        await Promise.all([openConnectionPromise1, openConnectionPromise2]);
        bus.trigger("webrtc_answer", { iot_box_identifier: "iot", answer: "mockAnswer" });
        bus.trigger("webrtc_answer", { iot_box_identifier: "iot2", answer: "mockAnswer2" });

        expect(MockRtcPeerConnection._instances).toBe(2);
        expect(webRtc.connections["iot"].connection.remoteDescription).toBe("mockAnswer");
        expect(webRtc.connections["iot2"].connection.remoteDescription).toBe("mockAnswer2");
    });
});

describe("sending message", () => {
    test("message is sent", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testValue" };

        await webRtc.sendMessage("iot", testMessage);

        expect(webRtc.connections["iot"].channel._messagesSent).toHaveLength(1);
        const sentMessage = JSON.parse(webRtc.connections["iot"].channel._messagesSent[0]);
        expect(sentMessage).toMatchObject(testMessage);
        expect(sentMessage.session_id).toBeOfType("string");
    });

    test("session_id is set if not provided", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testValue" };

        await webRtc.sendMessage("iot", testMessage);

        expect(webRtc.connections["iot"].channel._messagesSent).toHaveLength(1);
        const sentMessage = JSON.parse(webRtc.connections["iot"].channel._messagesSent[0]);
        expect(sentMessage.session_id).toBeOfType("string");
    });

    test("session_id and message_type are included in message", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testValue" };

        await webRtc.sendMessage("iot", testMessage, "testId", "test_type");

        expect(webRtc.connections["iot"].channel._messagesSent).toHaveLength(1);
        const sentMessage = JSON.parse(webRtc.connections["iot"].channel._messagesSent[0]);
        expect(sentMessage.session_id).toBe("testId");
        expect(sentMessage.message_type).toBe("test_type");
    });

    test("large messages are chunked", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testLongMessageToMakeChunkingBeRequired" };

        await webRtc.sendMessage("iot", testMessage, "testId", "test_type");

        expect(webRtc.connections["iot"].channel._messagesSent).toHaveLength(4);
        expect(webRtc.connections["iot"].channel._messagesSent[0]).toBe("chunked_start");
        expect(webRtc.connections["iot"].channel._messagesSent[3]).toBe("chunked_end");
        const fullMessage = JSON.parse(
            webRtc.connections["iot"].channel._messagesSent.slice(1, 3).join("")
        );
        expect(fullMessage).toMatchObject(testMessage);
    });

    test("throws if connection is disconnected", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testValue" };

        webRtc.connections["iot"].connection.connectionState = "disconnected";

        await expect(webRtc.sendMessage("iot", testMessage)).rejects.toMatch(
            "WebRTC connection for iot is 'disconnected'"
        );
    });

    test("throws if data channel is closed", async () => {
        const { webRtc } = await setupWebRtcWithConnection("iot");
        const testMessage = { testKey: "testValue" };

        webRtc.connections["iot"].channel.readyState = "closed";

        await expect(webRtc.sendMessage("iot", testMessage)).rejects.toMatch(
            "WebRTC channel for iot is 'closed'"
        );
    });
});
