import { EventBus, reactive } from "@odoo/owl";

import { CallMethodSelectionDialog } from "@voip/mobile/call_method_selection_dialog";
import { SoftphoneContainer } from "@voip/softphone/softphone_container";
import { Softphone } from "@voip/softphone/softphone_model";
import { cleanPhoneNumber } from "@voip/utils/utils";
import { VoipSystrayItem } from "@voip/web/voip_systray_item";

import { isMobileOS } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { Deferred } from "@web/core/utils/concurrency";

export class Voip {
    bus = new EventBus();
    callActivityTypeId;
    error;
    isUnloading = false;
    /**
     * Either “demo” or “prod”. In demo mode, phone calls are simulated in the
     * interface but no RTC sessions are actually established.
     *
     * @type {"demo"|"prod"}
     */
    mode;
    /**
     * The address of the PBX server. Used as the hostname in SIP URIs.
     *
     * @type {string}
     */
    pbxAddress;
    /** @type {"always"|"user"|"disabled"} */
    recordingPolicy;
    /** @type {Softphone} */
    softphone;
    /**
     * The WebSocket URL of the signaling server that will be used to
     * communicate SIP messages between Odoo and the PBX server.
     *
     * @type {string}
     */
    webSocketUrl;

    constructor(env, services) {
        this.env = env;
        /** @type {import("@mail/core/store_service").Store} */
        this.store = services["mail.store"];
        this.callService = services["voip.call"];
        this.dialog = services.dialog;
        this.orm = services.orm;
        this.busService = services.bus_service;
        this.softphone = new Softphone(this.store, this);
        this.callService.missedCalls = this.store.voipConfig?.missedCalls ?? 0;
        delete this.store.voipConfig?.missedCalls;
        Object.assign(this, this.store.voipConfig);
        delete this.store.voipConfig;
        this.busService.subscribe("delete_call_activity", (payload) => {
            const activity = this.store["mail.activity"].insert(payload);
            activity.remove();
        });
        this.busService.subscribe("refresh_call_activities", () => {
            this.fetchTodayCallActivities();
        });
        this.busService.subscribe("voip.call/delete", (payload) => {
            for (const id of payload.ids) {
                this.store["voip.call"].get(id)?.delete();
            }
        });
        window.addEventListener("beforeunload", this._onBeforeUnload.bind(this));
        return reactive(this);
    }

    /**
     * Determines if `voip_secret` and `voip_username` settings are defined for
     * the current user.
     *
     * @returns {boolean}
     */
    get areCredentialsSet() {
        return Boolean(this.store.settings.voip_username && this.store.settings.voip_secret);
    }

    /**
     * With some providers, the authorization username (the one used to register
     * with the PBX server) differs from the username. This getter is intended
     * to provide a way to override the authorization username.
     *
     * @returns {string}
     */
    get authorizationUsername() {
        return this.store.settings.voip_username || "";
    }

    get calls() {
        return this.store["voip.call"].records;
    }

    /** @returns {boolean} */
    get canCall() {
        return (
            this.mode === "demo" ||
            (this.hasRtcSupport && this.isServerConfigured && this.areCredentialsSet)
        );
    }

    /** @returns {boolean} */
    get hasPendingRequest() {
        return Boolean(this._activityRpc || this._contactRpc || this._recentCallsRpc);
    }

    /** @returns {boolean} */
    get hasRtcSupport() {
        return Boolean(window.RTCPeerConnection && window.MediaStream && navigator.mediaDevices);
    }

    /** @returns {boolean} */
    get hasValidExternalDeviceNumber() {
        if (!this.store.settings.external_device_number) {
            return false;
        }
        return cleanPhoneNumber(this.store.settings.external_device_number) !== "";
    }

    /**
     * Determines if `pbxAddress` and `webSocketUrl` have been provided.
     *
     * @returns {boolean}
     */
    get isServerConfigured() {
        return Boolean(this.pbxAddress && this.webSocketUrl);
    }

    /** @returns {number} */
    get missedCalls() {
        return this.callService.missedCalls;
    }

    /**
     * Determines if the `should_call_from_another_device` setting is set and if
     * an `external_device_number` has been provided.
     *
     * @returns {boolean}
     */
    get willCallFromAnotherDevice() {
        return (
            this.store.settings.should_call_from_another_device && this.hasValidExternalDeviceNumber
        );
    }

    async fetchContacts(searchTerms = "", offset = 0, limit = 13, t9Search = false) {
        if (this._contactRpc) {
            this._contactRpc.abort();
        }
        this._contactRpc = this.orm.call("res.partner", "get_contacts", [], {
            offset,
            limit,
            search_terms: searchTerms.trim(),
            t9_search: t9Search,
        });
        try {
            const data = await this._contactRpc;
            this.store.insert(data);
            this._contactRpc = null;
        } catch (error) {
            if (error.event?.type === "abort") {
                error.event.preventDefault();
                return;
            }
            if (error.message?.toLowerCase().includes("abort")) {
                // Unreliable, message content varies between browsers.
                return;
            }
            this._contactRpc = null;
            // Don't throw, it could still be an abort error that wasn't caught
            // by the conditions above.
            console.error(error);
        }
    }

    async fetchRecentCalls(searchTerms = "", offset = 0, limit = 13) {
        if (this._recentCallsRpc) {
            this._recentCallsRpc.abort();
        }
        this._recentCallsRpc = this.orm.call("voip.call", "get_recent_phone_calls", [], {
            offset,
            limit,
            search_terms: searchTerms.trim(),
        });
        try {
            const data = await this._recentCallsRpc;
            this.store.insert(data);
            this._recentCallsRpc = null;
        } catch (error) {
            if (error.event?.type === "abort") {
                error.event.preventDefault();
                return;
            }
            if (error.message?.toLowerCase().includes("abort")) {
                // Unreliable, message content varies between browsers.
                return;
            }
            this._recentCallsRpc = null;
            // Don't throw, it could still be an abort error that wasn't caught
            // by the conditions above.
            console.error(error);
        }
    }

    async fetchTodayCallActivities() {
        if (this._activityRpc) {
            return;
        }
        this._activityRpc = this.orm.call("mail.activity", "get_today_call_activities");
        try {
            const data = await this._activityRpc;
            this.store.insert(data);
        } finally {
            this._activityRpc = null;
        }
    }

    resetMissedCalls() {
        if (this.missedCalls !== 0) {
            this.orm.call("res.users", "reset_last_seen_phone_call");
        }
        this.callService.missedCalls = 0;
    }

    resolveError() {
        this.error = null;
    }

    /**
     * Triggers an error that will be displayed in the softphone, and blocks the
     * UI by default.
     *
     * @param {string} message The error message to be displayed.
     * @param {Object} [options={}]
     * @param {boolean} [options.isNonBlocking=false] If true, the error will
     * not block the UI.
     */
    triggerError(message, { isNonBlocking = false, title, button } = {}) {
        this.error = { title, text: message, isNonBlocking, button };
    }

    /** @returns {Deferred<boolean>} */
    async willCallUsingVoip() {
        if (!isMobileOS()) {
            return true;
        }
        const callMethod = this.store.settings.how_to_call_on_mobile;
        if (callMethod !== "ask") {
            return callMethod === "voip";
        }
        const useVoip = new Deferred();
        this.dialog.add(
            CallMethodSelectionDialog,
            { useVoip },
            { onClose: () => useVoip.resolve(true) }
        );
        return useVoip;
    }

    /**
     * @param {BeforeUnloadEvent} ev
     * @returns {string|undefined}
     */
    _onBeforeUnload(ev) {
        if (!this.env.services["voip.user_agent"]?.activeSession?.call.isInProgress) {
            return;
        }
        ev.preventDefault();
        return (ev.returnValue = _t(
            "There is still a call in progress, are you sure you want to leave the page?"
        ));
    }

    // TODO: remove
    fakeIncoming() {
        const fakeInvitation = {
            remoteIdentity: {
                uri: {
                    user: "+1 555-555-5555",
                },
            },
            incomingInviteRequest: {},
            stateChange: {
                addListener() {},
            },
        };
        this.env.services["voip.user_agent"]._onIncomingInvitation(fakeInvitation);
    }
}

export const voipService = {
    dependencies: ["bus_service", "dialog", "mail.store", "orm", "voip.call"],
    async start() {
        const isEmployee = await user.hasGroup("base.group_user");
        if (!isEmployee) {
            return {
                bus: new EventBus(),
                get canCall() {
                    return false;
                },
            };
        }
        registry.category("main_components").add("voip.SoftphoneContainer", {
            Component: SoftphoneContainer,
        });
        registry.category("systray").add("voip", { Component: VoipSystrayItem });
        return new Voip(...arguments);
    },
};

registry.category("services").add("voip", voipService);
