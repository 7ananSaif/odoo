/* global SIP */

import { Registerer } from "@voip/core/registerer";
import { Session } from "@voip/core/session";
import { cleanPhoneNumber } from "@voip/utils/utils";

import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Reactive } from "@web/core/utils/reactive";
import { session } from "@web/session";

export class UserAgent extends Reactive {
    /** @type {Session} */
    activeSession;
    attemptingToReconnect = false;
    /**
     * The id of the setTimeout used in demo mode to simulate the waiting time
     * before the call is picked up.
     *
     * @type {number}
     */
    demoTimeout;
    /** @type {Session} */
    mainSession;
    registerer;
    /**
     * The Audio element used to play the audio stream received from the remote
     * call party.
     *
     * @type {HTMLAudioElement}
     */
    remoteAudio = new window.Audio();
    /** @type {Session} */
    transferSession;
    voip;
    __sipJsUserAgent;

    constructor(env, services) {
        super();
        this.env = env;
        this.callService = services["voip.call"];
        this.multiTabService = services.multi_tab;
        this.ringtoneService = services["voip.ringtone"];
        this.voip = services.voip;
        this.softphone = this.voip.softphone;
        this.init();
    }

    /** @returns {boolean} */
    get hasCallInvitation() {
        const call = this.activeSession?.call;
        if (!call) {
            return false;
        }
        return call.state === "calling" && call.direction === "incoming";
    }

    /**
     * Provides the function that will be used by the SIP.js library to create
     * the media source that will serve as the local media stream (i.e. the
     * recording of the user's microphone).
     *
     * @returns {SIP.MediaStreamFactory}
     */
    get mediaStreamFactory() {
        return (constraints, sessionDescriptionHandler) => {
            const mediaRequest = navigator.mediaDevices.getUserMedia(constraints);
            mediaRequest.then(
                (stream) => this._onGetUserMediaSuccess(stream),
                (error) => this._onGetUserMediaFailure(error)
            );
            return mediaRequest;
        };
    }

    /** @returns {Object} */
    get sipJsUserAgentConfig() {
        const isDebug = odoo.debug !== "";
        return {
            authorizationPassword: this.voip.store.settings.voip_secret,
            authorizationUsername: this.voip.authorizationUsername,
            delegate: {
                onDisconnect: (error) => this._onTransportDisconnected(error),
                onInvite: (inviteSession) => this._onIncomingInvitation(inviteSession),
            },
            hackIpInContact: true,
            logBuiltinEnabled: isDebug,
            logLevel: isDebug ? "debug" : "error",
            sessionDescriptionHandlerFactory: SIP.Web.defaultSessionDescriptionHandlerFactory(
                this.mediaStreamFactory
            ),
            sessionDescriptionHandlerFactoryOptions: { iceGatheringTimeout: 1000 },
            transportOptions: {
                keepAliveInterval: 20,
                server: this.voip.webSocketUrl,
                traceSip: isDebug,
            },
            uri: SIP.UserAgent.makeURI(
                `sip:${this.voip.store.settings.voip_username}@${this.voip.pbxAddress}`
            ),
            userAgentString: `Odoo ${session.server_version} SIP.js/${window.SIP.version}`,
        };
    }

    get isInDoNotDisturbMode() {
        const dndUntil = this.voip.store.settings.do_not_disturb_until_dt;
        return Boolean(dndUntil) && dndUntil > luxon.DateTime.now();
    }

    async shouldPlayIncomingCallRingtone() {
        return (
            this.hasCallInvitation &&
            !this.isInDoNotDisturbMode &&
            (await this.multiTabService.isOnMainTab())
        );
    }

    async acceptIncomingCall() {
        this.ringtoneService.stopPlaying();
        this.voip.triggerError(_t("Please accept the use of the microphone."));
        // ⚠ Async code ahead. Save call here in case the one on this.activeSession
        // changes in the meantime.
        const call = this.activeSession.call;
        const isSrtpDtls = this._hasSrtpDtlsMediaType(this.activeSession.sipSession.body);
        const hasDtlsAttributes = this._hasDtlsAttributes(this.activeSession.sipSession.body);
        try {
            await this.activeSession.sipSession.accept({
                sessionDescriptionHandlerOptions: { constraints: Session.mediaConstraints },
            });
        } catch (error) {
            console.error(error);
            this.callService.end(call);
            const errorParts = [
                _t("An error occurred while attempting to answer the incoming call."),
            ];
            if (!hasDtlsAttributes) {
                errorParts.push(
                    _t(
                        "The DTLS fingerprint and/or setup is missing from the SDP. Please have your administrator verify that the PBX is configured to use SRTP-DTLS."
                    )
                );
            } else if (!isSrtpDtls) {
                errorParts.push(
                    _t(
                        "It appears that the server may not be using the correct media type. Please have your administrator verify that the media type is correctly set to SRTP-DTLS."
                    )
                );
            }
            errorParts.push(_t("Error message:\n%s", error.message));
            this.voip.triggerError(errorParts.join("\n\n"), { isNonBlocking: true });
        }
    }

    async attemptReconnection(attemptCount = 0) {
        if (this.voip.isUnloading) {
            return;
        }
        if (attemptCount > 5) {
            this.voip.triggerError(
                _t("The WebSocket connection was lost and couldn't be reestablished.")
            );
            return;
        }
        if (this.attemptingToReconnect) {
            return;
        }
        this.attemptingToReconnect = true;
        try {
            await this.__sipJsUserAgent.reconnect();
            this.registerer.register();
            this.voip.resolveError();
        } catch {
            setTimeout(
                () => this.attemptReconnection(attemptCount + 1),
                2 ** attemptCount * 1000 + Math.random() * 500
            );
        } finally {
            this.attemptingToReconnect = false;
        }
    }

    async hangup({ session = null, activityDone = true } = {}) {
        if (!session) {
            session = this.activeSession;
        }
        this.ringtoneService.stopPlaying();
        clearTimeout(this.demoTimeout);
        if (session.sipSession) {
            switch (session.sipSession.state) {
                case SIP.SessionState.Establishing:
                    session.sipSession.cancel();
                    break;
                case SIP.SessionState.Established:
                    session.sipSession.bye();
                    break;
            }
        }
        switch (session.call.state) {
            case "calling":
                await this.callService.abort(session.call);
                break;
            case "ongoing":
                await this.callService.end(session.call, { activityDone });
                break;
        }
    }

    async init() {
        if (this.voip.mode !== "prod") {
            return;
        }
        if (!this.voip.hasRtcSupport) {
            this.voip.triggerError(
                _t(
                    "Your browser does not support some of the features required for VoIP to work. Please try updating your browser or using a different one."
                )
            );
            return;
        }
        if (!this.voip.isServerConfigured) {
            this.voip.triggerError(
                _t("PBX or Websocket address is missing. Please check your settings.")
            );
            return;
        }
        if (!this.voip.areCredentialsSet) {
            this.voip.triggerError(
                _t("Your login details are not set correctly. Please contact your administrator.")
            );
            return;
        }
        try {
            await loadBundle("voip.assets_sip");
        } catch (error) {
            console.error(error);
            this.voip.triggerError(
                _t("Failed to load the SIP.js library:\n\n%(error)s", {
                    error: error.message,
                })
            );
            return;
        }
        try {
            this.__sipJsUserAgent = new SIP.UserAgent(this.sipJsUserAgentConfig);
        } catch (error) {
            console.error(error);
            this.voip.triggerError(
                _t("An error occurred during the instantiation of the User Agent:\n\n%(error)s", {
                    error: error.message,
                })
            );
            return;
        }
        this.voip.triggerError(_t("Connecting…"));
        try {
            await this.__sipJsUserAgent.start();
        } catch {
            this.voip.triggerError(
                _t(
                    "The user agent could not be started. The websocket server URL may be incorrect. Please have an administrator check the websocket server URL in the VoIP Provider Settings."
                )
            );
            return;
        }
        this.registerer = new Registerer(this.voip, this.__sipJsUserAgent);
        this.registerer.register();
    }

    /**
     * @param {import("@voip/core/call_model").Call} call
     * @returns {Session}
     */
    invite(call) {
        if (this.voip.mode === "demo") {
            const session = new Session(call);
            this.demoTimeout = setTimeout(() => {
                session._onOutgoingInviteAccepted();
            }, 3000);
            return session;
        }
        const phoneNumber = this.voip.willCallFromAnotherDevice
            ? this.voip.store.settings.external_device_number
            : call.phone_number;
        try {
            var inviter = new SIP.Inviter(this.__sipJsUserAgent, this.makeUri(phoneNumber));
        } catch (error) {
            console.error(error);
            this.voip.triggerError(
                _t(
                    "An error occurred trying to invite the following number: %(phoneNumber)s\n\nError: %(error)s",
                    { phoneNumber, error: error.message }
                )
            );
            throw error;
        }
        const session = new Session(call, inviter);
        if (this.voip.willCallFromAnotherDevice) {
            session.transferTarget = call.phone_number;
        }
        const sessionDescriptionHandlerOptions = { constraints: Session.mediaConstraints };
        inviter
            .invite({
                requestDelegate: session.inviteRequestDelegate,
                sessionDescriptionHandlerOptions,
            })
            .catch((error) => {
                if (error.name !== "NotAllowedError") {
                    throw error;
                }
            });
        return session;
    }

    /**
     * @param {Object} data
     * @param {Object} options
     * @param {string} options.type - The type of session to create --> "default" for the main session, "transfer" for the transfer session.
     */
    async makeCall(data, { type = "default" } = {}) {
        if (!(await this.voip.willCallUsingVoip())) {
            window.location.assign(`tel:${data.phone_number}`);
            return;
        }
        const call = await this.callService.create(data);
        try {
            var session = this.invite(call);
        } catch {
            this.callService.abort(call);
            return;
        }
        if (type === "transfer") {
            this.activeSession = this.transferSession = session;
        } else {
            this.activeSession = this.mainSession = session;
        }
        this.softphone.show();
        this.ringtoneService.ringback.play();
    }

    /**
     * @param {string} phoneNumber
     * @returns {SIP.URI}
     */
    makeUri(phoneNumber) {
        const sanitizedNumber = cleanPhoneNumber(phoneNumber);
        return SIP.UserAgent.makeURI(`sip:${sanitizedNumber}@${this.voip.pbxAddress}`);
    }

    async rejectIncomingCall() {
        this.ringtoneService.stopPlaying();
        this.activeSession.sipSession.reject({ statusCode: 603 /* Decline */ });
        await this.callService.reject(this.activeSession.call);
    }

    performAttendedTransfer() {
        if (this.voip.mode === "demo") {
            this.hangup({ session: this.mainSession });
            this.hangup({ session: this.transferSession });
            return;
        }
        if (this.mainSession && this.transferSession) {
            const mainSession = this.mainSession;
            mainSession.sipSession.refer(this.transferSession.sipSession, {
                onNotify: ({ incomingNotifyRequest }) => {
                    if (incomingNotifyRequest.message.body.includes("200 OK")) {
                        this.hangup({ session: mainSession });
                    }
                },
            });
        }
    }

    /**
     * Determines if the SDP contains the attributes required by DTLS.
     *
     * @param {string} sdp
     */
    _hasDtlsAttributes(sdp) {
        const fields = sdp.split(/\r?\n/);
        let hasFingerprint = false;
        let hasSetup = false;
        for (const field of fields) {
            hasFingerprint ||= field.startsWith("a=fingerprint");
            hasSetup ||= field.startsWith("a=setup");
        }
        return hasFingerprint && hasSetup;
    }

    /**
     * Determines if the media type for the audio is SRTP-DTLS.
     *
     * WebRTC mandates the use of "SRTP-DTLS", which means that RTP datagrams
     * must be encrypted using TLS (DTLS).
     *
     * Note that communication could still work with a "plain RTC" media type,
     * as long as the DTLS fingerprint is included.
     *
     * @param {string} sdp
     * @returns {boolean}
     */
    _hasSrtpDtlsMediaType(sdp) {
        const fields = sdp.split(/\r?\n/);
        return fields.some(
            (field) => field.startsWith("m=audio") && field.includes("UDP/TLS/RTP/SAVPF")
        );
    }

    /** @param {DOMException} error */
    _onGetUserMediaFailure(error) {
        console.error(error);
        const errorMessage = (() => {
            switch (error.name) {
                case "NotAllowedError":
                    return _t(
                        "Cannot access audio recording device. If you have denied access to your microphone, please allow it and try again. Otherwise, make sure that this website is running over HTTPS and that your browser is not set to deny access to media devices."
                    );
                case "NotFoundError":
                    return _t(
                        "No audio recording device available. The application requires a microphone in order to be used."
                    );
                case "NotReadableError":
                    return _t(
                        "A hardware error has occurred while trying to access the audio recording device. Please ensure that your drivers are up to date and try again."
                    );
                default:
                    return _t(
                        "An error occured involving the audio recording device (%(errorName)s):\n%(errorMessage)s",
                        { errorMessage: error.message, errorName: error.name }
                    );
            }
        })();
        this.voip.triggerError(errorMessage, { isNonBlocking: true });
        if (this.activeSession.call.direction === "outgoing") {
            this.hangup();
        } else {
            this.rejectIncomingCall();
        }
    }

    /** @param {MediaStream} stream */
    _onGetUserMediaSuccess(stream) {
        this.voip.resolveError();
        switch (this.activeSession.call.direction) {
            case "outgoing":
                this.ringtoneService.dial.play();
                break;
            case "incoming":
                this.callService.start(this.activeSession.call);
                break;
        }
    }

    /** @param {Object} inviteSession */
    async _onIncomingInvitation(inviteSession) {
        if (this.activeSession) {
            inviteSession.reject({ statusCode: 486 /* Busy Here */ });
            return;
        }
        const phoneNumber = inviteSession.remoteIdentity.uri.user;
        const call = await this.callService.create({
            direction: "incoming",
            phone_number: phoneNumber,
        });
        const session = new Session(call, inviteSession);
        inviteSession.incomingInviteRequest.delegate = {
            onCancel: (message) => session._onIncomingInviteCanceled(message),
        };
        this.activeSession = this.mainSession = session;
        if (!this.isInDoNotDisturbMode) {
            this.softphone.show();
        }
        if (await this.shouldPlayIncomingCallRingtone()) {
            this.ringtoneService.incoming.play();
        }
    }

    /**
     * Triggered when the transport transitions from connected state.
     *
     * @param {Error} error
     */
    _onTransportDisconnected(error) {
        if (!error) {
            return;
        }
        console.error(error);
        this.voip.triggerError(
            _t(
                "The websocket connection to the server has been lost. Attempting to reestablish the connection…"
            )
        );
        this.attemptReconnection();
    }
}

export const userAgentService = {
    dependencies: ["multi_tab", "voip", "voip.call", "voip.ringtone"],
    start(env, services) {
        return new UserAgent(env, services);
    },
};

registry.category("services").add("voip.user_agent", userAgentService);
