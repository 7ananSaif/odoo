/* global SIP */

import { reactive } from "@odoo/owl";

import { Deferred } from "@web/core/utils/concurrency";

export class SessionRecorder {
    /** @type {Map<string, string>} */
    static EXTENSION_BY_MIMETYPE = new Map([
        ["audio/aac", "aac"],
        ["audio/mpeg", "mp3"],
        ["audio/ogg", "ogg"],
        ["audio/wav", "wav"],
        ["audio/webm", "webm"],
    ]);
    /**
     * Useful for preventing the garbage-collection of SessionRecorder instances
     * until _onStop is called.
     *
     * @type {Set<SessionRecorder>}
     */
    static pendingRecordings = new Set();
    /** @type {Set<Promise<Response>>} */
    static pendingUploads = reactive(new Set());
    /**
     * Most preferred types come first.
     *
     * @type {string[]}
     */
    static PREFERRED_MIMETYPES = [
        "audio/mpeg",
        "audio/webm;codecs=opus",
        "audio/ogg;codecs=opus",
        "audio/aac",
        "audio/wav", // uncompressed, last resort
    ];

    /** @type {Deferred<File>} */
    file = new Deferred();
    /** @type {AudioContext|null} */
    _audioContext;
    /** @type {Blob[]} */
    _chunks = [];

    constructor(sipSession) {
        const { audioContext, stream } = SessionRecorder.mergeStreams(sipSession);
        this._audioContext = audioContext;
        const recorder = new MediaRecorder(stream, {
            audioBitsPerSecond: 8000, // bitrate of G.729 (widely used codec for VoIP)
            mimeType: this.outputMimeType,
        });
        recorder.addEventListener("stop", (event) => this._onStop(event));
        recorder.addEventListener("dataavailable", (event) => this._onDataAvailable(event));
        recorder.addEventListener("error", (event) => this._onError(event));
        sipSession.stateChange.addListener((state) => {
            if (state === SIP.SessionState.Terminated) {
                this.stop();
            }
        });
        this._recorder = recorder;
    }

    /**
     * @param {SIP.Session} sipSession
     * @returns {{ audioContext: AudioContext, stream: MediaStream }}
     */
    static mergeStreams(sipSession) {
        const micTrack = sipSession.sessionDescriptionHandler.peerConnection
            .getSenders()
            .find((sender) => sender.track.kind === "audio").track;
        const localStream = new MediaStream([micTrack]);
        const remoteStream = sipSession.sessionDescriptionHandler.remoteMediaStream;
        const audioContext = new AudioContext();
        const mergedAudio = new MediaStreamAudioDestinationNode(audioContext, {
            // down-mix to mono, using pre-defined mixing rules
            channelCount: 1,
            channelCountMode: "explicit",
            channelInterpretation: "speakers",
        });
        const localSource = audioContext.createMediaStreamSource(localStream);
        const remoteSource = audioContext.createMediaStreamSource(remoteStream);
        // add gain to reduce clipping
        const gain = 1 / Math.sqrt(2);
        localSource.connect(new GainNode(audioContext, { gain })).connect(mergedAudio);
        remoteSource.connect(new GainNode(audioContext, { gain })).connect(mergedAudio);
        return { audioContext, stream: mergedAudio.stream };
    }

    /**
     * @param {string|URL|Request} url
     * @param {File} file
     * @param {Function} [param2.onFailure]
     * @param {Function} [param2.onSuccess]
     * @returns {Promise}
     */
    static async upload(url, file, { onFailure, onSuccess } = {}) {
        const formData = new FormData();
        formData.append("csrf_token", odoo.csrf_token);
        formData.append("ufile", file);
        let response = null;
        let error = null;
        const promise = fetch(url, { method: "POST", body: formData });
        SessionRecorder.pendingUploads.add(promise);
        try {
            response = await promise;
        } catch (err) {
            console.error(err);
            error = err;
        } finally {
            SessionRecorder.pendingUploads.delete(promise);
        }
        if (error || !response.ok) {
            onFailure?.(response, error);
            return;
        }
        onSuccess?.();
    }

    /** @returns {string} */
    get outputFileExtension() {
        const mimeType = this._recorder.mimeType.split(";")[0];
        return SessionRecorder.EXTENSION_BY_MIMETYPE.get(mimeType) ?? "bin";
    }

    /** @returns {string} */
    get outputMimeType() {
        for (const mimeType of SessionRecorder.PREFERRED_MIMETYPES) {
            if (MediaRecorder.isTypeSupported(mimeType)) {
                return mimeType;
            }
        }
        return ""; // let browser pick
    }

    /** @returns {"inactive"|"paused"|"recording"} */
    get state() {
        return this._recorder.state;
    }

    pause() {
        this._recorder.pause();
    }

    resume() {
        this._recorder.resume();
    }

    start() {
        this._recorder.start();
        SessionRecorder.pendingRecordings.add(this._recorder);
    }

    stop() {
        if (this.state !== "inactive") {
            this._recorder.stop();
        }
    }

    _disposeAudioContext() {
        if (!this._audioContext) {
            return;
        }
        if (this._audioContext.state !== "closed") {
            this._audioContext.close();
        }
        this._audioContext = null;
    }

    _onDataAvailable({ data }) {
        this._chunks.push(data);
    }

    _onError({ error }) {
        this.file.reject(error);
        this._disposeAudioContext();
    }

    _onStop(event) {
        SessionRecorder.pendingRecordings.delete(this._recorder);
        const file = new File(this._chunks, `recording.${this.outputFileExtension}`, {
            type: this.outputMimeType,
        });
        this.file.resolve(file);
        this._disposeAudioContext();
    }
}
