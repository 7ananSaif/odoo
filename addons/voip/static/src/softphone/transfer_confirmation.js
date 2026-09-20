import { Component } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";
import { ContactInfo } from "@voip/softphone/contact_info";

import { useService } from "@web/core/utils/hooks";

export class TransferConfirmation extends Component {
    static components = { ActionButton, ContactInfo };
    static props = {
        call: Object,
        targetContact: [Object, Boolean],
        targetPhoneNumber: String,
    };
    static template = "voip.TransferConfirmation";

    setup() {
        this.userAgent = useService("voip.user_agent");
        this.softphone = useService("voip").softphone;
    }

    onClickDirectTransfer() {
        this.userAgent.activeSession.blindTransfer(this.props.targetPhoneNumber);
    }

    async onClickAskFirst() {
        this.userAgent.activeSession.isOnHold = true;
        await this.userAgent.makeCall(
            {
                phone_number: this.props.targetPhoneNumber,
                partner: this.props.targetContact,
            },
            {
                type: "transfer",
            }
        );
        this.softphone.inCallView.activeView = "default";
        this.softphone.inCallView.transferView.activeView = "contacts";
    }

    onClickCancel() {
        this.softphone.inCallView.transferView.activeView = "contacts";
    }
}
