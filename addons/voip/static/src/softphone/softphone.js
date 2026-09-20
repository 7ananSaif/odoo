import { Component, useState } from "@odoo/owl";

import { AddressBook } from "@voip/softphone/address_book";
import { Agenda } from "@voip/softphone/agenda";
import { CallBanner } from "@voip/softphone/call_banner";
import { CallInvitation } from "@voip/softphone/call_invitation";
import { CallSummary } from "@voip/softphone/call_summary";
import { Dialer } from "@voip/softphone/dialer";
import { DndSelector } from "@voip/softphone/dnd_selector";
import { ErrorScreen } from "@voip/softphone/error_screen";
import { History } from "@voip/softphone/history";
import { InCallView } from "@voip/softphone/in_call_view";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class Softphone extends Component {
    static components = {
        AddressBook,
        Agenda,
        CallBanner,
        CallInvitation,
        Dialer,
        DndSelector,
        ErrorScreen,
        CallSummary,
        History,
        InCallView,
    };
    static props = {};
    static template = "voip.Softphone";

    setup() {
        this.userAgent = useService("voip.user_agent");
        this.ringtoneService = useService("voip.ringtone");
        this.voip = useService("voip");

        this.softphone = useState(this.voip.softphone);
    }

    /** @returns {string} */
    get activeTab() {
        return this.softphone.activeTab;
    }

    /** @returns {import("@voip/core/call_model").Call} */
    get bannerCall() {
        return this.userAgent.activeSession === this.userAgent.mainSession
            ? this.userAgent.transferSession.call
            : this.userAgent.mainSession.call;
    }

    /** @returns {boolean} */
    get isOnSmallDevice() {
        return this.env.services.ui.isSmall;
    }

    get pendingCall() {
        return this.userAgent.activeSession?.call;
    }

    /** @returns {boolean} */
    get shouldShowCallBanner() {
        return (
            this.userAgent.mainSession &&
            this.userAgent.transferSession &&
            this.pendingCall.state === "ongoing"
        );
    }

    get tabs() {
        return [
            { id: "dialer", name: _t("Keypad"), icon: "oi oi-numpad" },
            { id: "recent", name: _t("Recent"), icon: "fa fa-history" },
            { id: "contacts", name: _t("Contacts"), icon: "fa fa-address-book-o" },
            { id: "activities", name: _t("Activities"), icon: "fa fa-clock-o" },
        ];
    }

    /** @returns {string} */
    get topBarIcon() {
        if (this.userAgent.activeSession?.isOnHold) {
            return "fa fa-pause text-warning";
        }
        return "oi oi-voip text-success";
    }

    /** @returns {string} */
    get topBarText() {
        if (!this.pendingCall) {
            return "";
        }
        if (this.userAgent.hasCallInvitation) {
            return _t("Incoming call…");
        }
        if (this.userAgent.activeSession?.inviteState === "ringing") {
            return _t("Ringing…");
        }
        if (this.pendingCall.state === "calling") {
            return _t("Outgoing call…");
        }
        if (this.pendingCall.state === "ongoing") {
            return _t("%(status)s - %(timer)s", {
                status: this.userAgent.activeSession.statusText,
                timer: this.pendingCall.timerText,
            });
        }
        return _t("In call");
    }

    /** @param {MouseEvent} ev */
    onClickClose(ev) {
        this.softphone.hide();
        if (this.userAgent.hasCallInvitation) {
            this.ringtoneService.stopPlaying();
        }
    }

    /** @param {string} tabId */
    onClickTab(tabId) {
        this.softphone.hideCallSummary();
        this.softphone.activeTab = tabId;
        this.softphone.shouldFocus = true;
    }
}
