import { Component, useState } from "@odoo/owl";

import { Call } from "@voip/core/call_model";
import { ActionButton } from "@voip/softphone/action_button";
import { ContactInfo } from "@voip/softphone/contact_info";
import { Keypad } from "@voip/softphone/keypad";
import { TransferConfirmation } from "@voip/softphone/transfer_confirmation";
import { TransferView } from "@voip/softphone/transfer_view";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class InCallView extends Component {
    static components = { ActionButton, ContactInfo, Keypad, TransferConfirmation, TransferView };
    static props = { call: Call };
    static template = "voip.InCallView";

    setup() {
        this.action = useService("action");
        this.voip = useService("voip");
        this.softphone = this.voip.softphone;
        this.userAgent = useService("voip.user_agent");
        this.ui = useService("ui");
        this.state = useState({
            targetContact: false,
            targetPhoneNumber: "",
        });
    }

    /** @returns {string} */
    get activeView() {
        return this.softphone.inCallView.activeView;
    }

    /** @returns {boolean} */
    get hasPendingTransfer() {
        return (
            this.userAgent.mainSession &&
            this.userAgent.transferSession &&
            this.userAgent.activeSession.call.state === "ongoing"
        );
    }

    /** @returns {boolean} */
    get isKeypadOpen() {
        return this.softphone.inCallView.keypad.isOpen;
    }

    /** @returns {boolean} */
    get isOnHold() {
        return this.userAgent.activeSession.isOnHold;
    }

    /** @returns {boolean} */
    get isMuted() {
        return this.userAgent.activeSession.isMuted;
    }

    /** @returns {boolean} */
    get isRecording() {
        const recorder = this.userAgent.activeSession.recorder;
        if (!recorder) {
            return false;
        }
        return recorder.state === "recording";
    }

    /** @returns {ReturnType<_t>} */
    get recordButtonName() {
        return this.isRecording ? _t("Stop") : _t("Record");
    }

    /** @returns {ReturnType<_t>|""} */
    get recordingIndicatorTitle() {
        if (this.voip.recordingPolicy === "always") {
            return _t("Enforced by admin");
        }
        return "";
    }

    onClickContact(ev) {
        const action = {
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
            context: {},
        };
        if (this.props.call.partner_id) {
            action.res_id = this.props.call.partner_id.id;
        } else {
            action.context.default_phone = this.props.call.phone_number;
        }
        this.action.doAction(action);
    }

    onClickHangUp() {
        this.userAgent.hangup();
    }

    onClickHold() {
        this.userAgent.activeSession.isOnHold = !this.isOnHold;
    }

    onClickKeypad() {
        this.softphone.inCallView.keypad.isOpen = !this.isKeypadOpen;
    }

    onClickMute() {
        this.userAgent.activeSession.isMuted = !this.userAgent.activeSession.isMuted;
    }

    onClickTransfer() {
        this.softphone.inCallView.activeView = "transfer";
        this.softphone.addressBook.searchInputValue = "";
    }

    onClickConfirmTransfer() {
        this.userAgent.performAttendedTransfer();
    }

    onClickTransferContacts() {
        this.softphone.inCallView.transferView.activeView = "contacts";
    }

    onClickTransferKeypad() {
        this.softphone.inCallView.transferView.activeView = "keypad";
        this.softphone.inCallView.transferView.keypad.input.focus = true;
    }

    onClickTransferPhone() {
        this.state.targetContact = false;
        this.state.targetPhoneNumber =
            this.softphone.inCallView.transferView.keypad.input.value.trim();
        this.softphone.inCallView.transferView.activeView = "confirmation";
    }

    onClickTransferContact(contact) {
        this.state.targetContact = contact;
        this.state.targetPhoneNumber = contact.phone;
        this.softphone.inCallView.transferView.activeView = "confirmation";
    }

    toggleRecording() {
        if (this.voip.recordingPolicy !== "user") {
            return;
        }
        const recorder = this.userAgent.activeSession.recorder;
        if (!recorder) {
            this.userAgent.activeSession.record();
            return;
        }
        switch (recorder.state) {
            case "paused":
                recorder.resume();
                break;
            case "recording":
                recorder.pause();
                break;
        }
    }
}
