/* global SIP */

import { toRaw } from "@odoo/owl";

import { SessionRecorder } from "@voip/core/session_recorder";

import { _t } from "@web/core/l10n/translation";

export class Session {
    /** @type {WeakSet<Session>} */
    static allSessions = new WeakSet();
    static get mediaConstraints() {
        const constraints = { audio: true, video: false };
        if (Session.preferredInputDevice) {
            constraints.audio = { deviceId: { exact: Session.preferredInputDevice } };
        }
        return constraints;
    }
    /**
     * The ID of the device the user wants to use to capture the voice.
     * Mobile only ⚠
     *
     * @type {string};
     */
    static preferredInputDevice = "";

    /** @type {import("@voip/core/call_service").CallService} */
    callService;
    /**
     * Only defined on sessions associated with an outbound call.
     *
     * @type {"trying"|"ringing"|"ok"|undefined}
     */
    inviteState;
    /** @type {SessionRecorder} */
    recorder;
    /**
     * The HTMLAudioElement through which the remote audio (remote peer's voice)
     * will be played.
     *
     * @type {HTMLAudioElement|null}
     */
    remoteAudio = null;
    /** @type {string|undefined} */
    transferTarget;
    /** @type {import("@voip/core/call_model").Call} */
    _call;
    /** @type {boolean} */
    _isOnHold = false;
    /** @type {boolean} */
    _isMuted = false;
    /**
     * The equivalent object from the SIP.js library.
     * null in demo mode.
     *
     * @type {SIP.Session|null}
     */
    _sipSession = null;

    constructor(call, sipSession = null) {
        if (!call) {
            throw new Error("Required argument 'call' is missing.");
        }
        Session.allSessions.add(this);
        this._call = call;
        if (call.direction === "outgoing") {
            this.inviteState = "trying";
        }
        const services = call.store.env.services;
        this.callService = services["voip.call"];
        this.ringtones = services["voip.ringtone"];
        this.userAgent = services["voip.user_agent"];
        this.voip = services.voip;
        if (!sipSession) {
            return this;
        }
        sipSession.delegate = { onBye: () => this.callService.end(this.call) };
        sipSession.stateChange.addListener((state) => this._onSessionStateChange(state));
        this._sipSession = sipSession;
    }

    /** @type {import("@voip/core/call_model").Call} */
    get call() {
        return this._call;
    }

    get inviteRequestDelegate() {
        return {
            onAccept: (response) => this._onOutgoingInviteAccepted(response),
            onProgress: (response) => this._onOutgoingInviteProgress(response),
            onReject: (response) => this._onOutgoingInviteRejected(response),
        };
    }

    /**
     * Determines whether the session is the one currently displayed in the
     * Softphone.
     *
     * @returns {boolean}
     */
    get isActiveSession() {
        return toRaw(this.userAgent.activeSession) === toRaw(this);
    }

    /** @returns {boolean} */
    get isOnHold() {
        return this._isOnHold;
    }

    /** @param {boolean} state */
    set isOnHold(state) {
        this._isOnHold = state;
        if (this.sipSession) {
            this._requestHold(state);
            this.updateTracks();
        }
    }

    /** @returns {boolean} */
    get isMuted() {
        return this._isMuted;
    }

    /** @param {boolean} state */
    set isMuted(state) {
        this._isMuted = state;
        this.updateTracks();
    }

    /** @returns {SIP.Session|null} */
    get sipSession() {
        return this._sipSession;
    }

    /** @returns {ReturnType<_t>|""} */
    get statusText() {
        if (this.isOnHold) {
            return _t("On hold");
        }
        if (this.voip.mode === "demo") {
            return _t("Demo call");
        }
        return _t("Calling…");
    }

    /**
     * Switches the device from which the voice is captured.
     * Might prompt the user for permission.
     * Future calls will use the selected device.
     *
     * @param {string} deviceId
     */
    static async switchInputDevice(deviceId) {
        Session.preferredInputDevice = deviceId;
        const stream = await navigator.mediaDevices.getUserMedia(Session.mediaConstraints);
        for (const session of Session.allSessions) {
            const peerConnection = session.sipSession?.sessionDescriptionHandler.peerConnection;
            if (!peerConnection) {
                continue;
            }
            for (const sender of peerConnection.getSenders()) {
                if (sender.track) {
                    await sender.replaceTrack(stream.getAudioTracks()[0]);
                }
            }
            session.updateTracks();
        }
    }

    /**
     * Performs a "blind transfer", i.e., instructs the remote party to connect
     * to the given "transferTarget" by sending a REFER request. It is called
     * "blind" because, once the REFER request has been accepted, the call is
     * immediately terminated regardless of whether the transfer succeeded.
     *
     * @param {string} transferTarget
     */
    blindTransfer(transferTarget) {
        this.voip.softphone.addressBook.searchInputValue = "";
        if (!this.sipSession) {
            this.userAgent.hangup({ session: this });
            return;
        }
        this.sipSession.refer(this.userAgent.makeUri(transferTarget), {
            requestDelegate: {
                onAccept: (response) => {
                    this.userAgent.hangup({ session: this });
                },
            },
        });
    }

    /**
     * Starts recording the audio of the session.
     * Once the recording stops, the file is automatically uploaded.
     */
    record() {
        if (this.recorder) {
            console.warn("Session.record() called on a session that already had a recorder.");
            return;
        }
        if (!this.sipSession) {
            return; // no session in demo mode
        }
        this.recorder = new SessionRecorder(this.sipSession);
        this.recorder.start();
        this.recorder.file.then((recording) =>
            SessionRecorder.upload(`/voip/upload_recording/${this.call.id}`, recording)
        );
    }

    updateTracks() {
        const sessionDescriptionHandler = this.sipSession?.sessionDescriptionHandler;
        if (!sessionDescriptionHandler?.peerConnection) {
            return;
        }
        sessionDescriptionHandler.enableReceiverTracks(!this.isOnHold);
        sessionDescriptionHandler.enableSenderTracks(!this.isOnHold && !this.isMuted);
    }

    /**
     * Explicitly resets the source and stops playback of the remote audio to
     * ensure that it can be garbage-collected.
     */
    _cleanUpRemoteAudio() {
        if (!this.remoteAudio) {
            return;
        }
        this.remoteAudio.pause();
        this.remoteAudio.srcObject.getTracks().forEach((track) => track.stop());
        this.remoteAudio.srcObject = null;
        this.remoteAudio.load();
        this.remoteAudio = null;
    }

    /**
     * Triggered when receiving CANCEL request.
     * Useful to handle missed phone calls.
     *
     * @param {SIP.IncomingRequestMessage} message
     */
    _onIncomingInviteCanceled() {
        if (this.isActiveSession) {
            this.ringtones.stopPlaying();
            this.voip.softphone.activeTab = "recent";
        }
        this.sipSession.reject({ statusCode: 487 /* Request Terminated */ });
        this.callService.miss(this.call);
    }

    /**
     * Triggered when receiving a 2xx final response to the INVITE request.
     *
     * @param {SIP.IncomingResponse} response
     */
    _onOutgoingInviteAccepted(response) {
        this.inviteState = "ok";
        if (this.isActiveSession) {
            this.ringtones.stopPlaying();
        }
        if (this.voip.willCallFromAnotherDevice) {
            this.blindTransfer(this.transferTarget);
            return;
        }
        this.callService.start(this.call);
    }

    /**
     * Triggered when receiving a 1xx provisional response to the INVITE request
     * (excepted code 100 responses).
     *
     * NOTE: Relying on provisional responses to implement behaviors seems like
     * a bad idea, as they may or may not be sent depending on the SIP server
     * implementation.
     *
     * @param {SIP.IncomingResponse} response
     */
    _onOutgoingInviteProgress(response) {
        const { statusCode } = response.message;
        if (statusCode === 183 /* Session Progress */ || statusCode === 180 /* Ringing */) {
            if (this.isActiveSession) {
                this.ringtones.ringback.play();
            }
            this.inviteState = "ringing";
        }
    }

    /**
     * Triggered when receiving a 4xx, 5xx, or 6xx final response to the
     * INVITE request.
     *
     * @param {SIP.IncomingResponse} response
     */
    _onOutgoingInviteRejected(response) {
        if (this.isActiveSession) {
            this.ringtones.stopPlaying();
        }
        if (response.message.statusCode === 487 /* Request Terminated */) {
            // invitation has been canceled by the user, the session has
            // already been terminated
            return;
        }
        const errorMessage = (() => {
            switch (response.message.statusCode) {
                case 404: // Not Found
                case 488: // Not Acceptable Here
                case 603: // Decline
                    return _t(
                        "The number is incorrect, the user credentials could be wrong or the connection cannot be made. Please check your configuration.\n(Reason received: %(reasonPhrase)s)",
                        { reasonPhrase: response.message.reasonPhrase }
                    );
                case 486: // Busy Here
                case 600: // Busy Everywhere
                    return _t("The person you try to contact is currently unavailable.");
                default:
                    return _t("Call rejected (reason: “%(reasonPhrase)s”)", {
                        reasonPhrase: response.message.reasonPhrase,
                    });
            }
        })();
        this.voip.triggerError(errorMessage, { isNonBlocking: true });
        this.callService.reject(this.call);
    }

    /**
     * Triggered when the state of the SIP.js session changes to Established.
     * Only triggered by actual RTC sessions (production mode).
     */
    _onSessionEstablished() {
        this._setUpRemoteAudio();
        this.sipSession.sessionDescriptionHandler.remoteMediaStream.onaddtrack = (
            mediaStreamTrackEvent
        ) => this._setUpRemoteAudio();
        if (this.voip.recordingPolicy === "always") {
            this.record();
        }
    }

    /** @param {SIP.SessionState} newState */
    _onSessionStateChange(newState) {
        switch (newState) {
            case SIP.SessionState.Initial:
                break;
            case SIP.SessionState.Establishing:
                break;
            case SIP.SessionState.Established:
                this._onSessionEstablished();
                break;
            case SIP.SessionState.Terminating:
                break;
            case SIP.SessionState.Terminated: {
                this._onSessionTerminated();
                break;
            }
            default:
                throw new Error(`Unknown session state: "${newState}".`);
        }
    }

    /**
     * Triggered when the state of the SIP.js session changes to Terminated.
     * Only triggered by actual RTC sessions (production mode).
     */
    _onSessionTerminated() {
        this._cleanUpRemoteAudio();
    }

    /**
     * Requests the remote peer to put the session on hold / resume it.
     *
     * @param {boolean} state `true` to put on hold, `false` to resume.
     */
    async _requestHold(state) {
        try {
            await this.sipSession.invite({
                requestDelegate: {
                    onAccept: () => {
                        this._isOnHold = state;
                    },
                },
                sessionDescriptionHandlerOptions: { hold: state },
            });
        } catch (error) {
            console.error(error);
            let errorMessage;
            if (state === true) {
                errorMessage = _t("Error putting the call on hold:");
            } else {
                errorMessage = _t("Error resuming the call:");
            }
            errorMessage += "\n\n" + error.message;
            this.voip.triggerError(errorMessage, { isNonBlocking: true });
        }
    }

    _setUpRemoteAudio() {
        const remoteAudio = new Audio();
        const remoteStream = new MediaStream();
        const receivers = this.sipSession.sessionDescriptionHandler.peerConnection.getReceivers();
        for (const { track } of receivers) {
            if (track) {
                remoteStream.addTrack(track);
            }
        }
        this.updateTracks();
        remoteAudio.srcObject = remoteStream;
        this._cleanUpRemoteAudio();
        this.remoteAudio = remoteAudio;
        remoteAudio.play();
    }
}
