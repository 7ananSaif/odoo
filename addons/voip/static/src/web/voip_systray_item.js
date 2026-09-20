import { Component, useState } from "@odoo/owl";

import { SessionRecorder } from "@voip/core/session_recorder";

import { useCommand } from "@web/core/commands/command_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class VoipSystrayItem extends Component {
    static props = {};
    static template = "voip.SystrayItem";

    setup() {
        this.voip = useService("voip");
        this.ringtoneService = useService("voip.ringtone");
        this.userAgent = useService("voip.user_agent");
        this.softphone = this.voip.softphone;
        this.pendingUploads = useState(SessionRecorder.pendingUploads);
        useCommand(_t("Toggle Softphone"), () => this.toggleSoftphone(), { hotkey: "Alt+Shift+S" });
    }

    /** @returns {boolean} */
    get hasOngoingCall() {
        const call = this.userAgent.activeSession?.call;
        if (!call) {
            return false;
        }
        return call.isInProgress && call.state === "ongoing";
    }

    /** @returns {string} */
    get iconClass() {
        if (this.userAgent.activeSession?.isOnHold) {
            return "fa fa-pause";
        }
        return "oi oi-voip";
    }

    /**
     * Number of missed calls used to display in systray item icon.
     *
     * @returns {number}
     */
    get missedCallCount() {
        return this.voip.missedCalls;
    }

    /**
     * Translated text used as the title attribute of the systray item.
     *
     * @returns {string}
     */
    get titleText() {
        return this.softphone.isDisplayed ? _t("Hide Softphone") : _t("Show Softphone");
    }

    /** @returns {string} */
    get systrayButtonClasses() {
        if (this.userAgent.hasCallInvitation) {
            return "text-success";
        }
        if (this.pendingUploads.size !== 0) {
            return "rounded-pill px-2 bg-warning text-warning-emphasis";
        }
        if (this.userAgent.activeSession?.isOnHold) {
            return "rounded-pill px-2 bg-warning-subtle text-warning-emphasis";
        }
        if (this.hasOngoingCall) {
            return "rounded-pill px-2 bg-success-subtle text-success-emphasis";
        }
        return "";
    }

    /** @returns {ReturnType<_t>|""} */
    get systrayButtonText() {
        if (SessionRecorder.pendingUploads.size !== 0) {
            return _t("Processing…");
        }
        return this.userAgent.activeSession?.statusText ?? "";
    }

    /** @param {MouseEvent} ev */
    onClick(ev) {
        this.toggleSoftphone();
    }

    async toggleSoftphone() {
        if (this.softphone.isDisplayed) {
            this.softphone.hide();
            if (this.userAgent.hasCallInvitation) {
                this.ringtoneService.stopPlaying();
            }
        } else {
            document.activeElement.blur();
            if (this.voip.missedCalls > 0) {
                this.softphone.activeTab = "recent";
                this.voip.resetMissedCalls();
            }
            this.softphone.show();
            if (await this.userAgent.shouldPlayIncomingCallRingtone()) {
                this.ringtoneService.incoming.play();
            }
        }
    }
}
