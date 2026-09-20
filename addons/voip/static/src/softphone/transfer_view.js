import { Component } from "@odoo/owl";

import { ActionButton } from "@voip/softphone/action_button";
import { AddressBook } from "@voip/softphone/address_book";
import { Keypad } from "@voip/softphone/keypad";
import { useService } from "@web/core/utils/hooks";

export class TransferView extends Component {
    static components = { ActionButton, AddressBook, Keypad };
    static props = {
        state: Object,
        onClickTransferContact: Function,
        onClickTransferPhone: Function,
    }; // TODO: type
    static template = "voip.TransferView";

    setup() {
        this.softphone = useService("voip").softphone;
        this.userAgent = useService("voip.user_agent");
        this.settings = useService("mail.store").settings;
        this.props.state.keypad.input.value ||= this.settings.external_device_number || "";
    }

    onClickBack() {
        this.softphone.inCallView.activeView = "default";
    }
}
