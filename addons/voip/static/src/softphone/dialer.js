import { Component } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";
import { Keypad } from "@voip/softphone/keypad";

import { useService } from "@web/core/utils/hooks";

export class Dialer extends Component {
    static components = { ActionButton, Keypad };
    static props = {};
    static template = "voip.Dialer";

    setup() {
        this.userAgentService = useService("voip.user_agent");
        this.softphone = useService("voip").softphone;
        this.softphone.dialer.input.focus = true;
    }

    /** @param {MouseEvent} ev */
    onClickCall(ev) {
        const inputValue = this.softphone.dialer.input.value.trim();
        if (!inputValue) {
            return;
        }
        this.userAgentService.makeCall({ phone_number: inputValue });
    }

    onClickKeypadFirstResult(contact) {
        this.userAgentService.makeCall({ partner: contact, phone_number: contact.phone });
    }
}
