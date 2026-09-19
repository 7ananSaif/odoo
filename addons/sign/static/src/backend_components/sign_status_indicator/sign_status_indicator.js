/** @odoo-module **/

import { Component } from "@odoo/owl";

export class SignStatusIndicator extends Component {
    static template = "sign.SignStatusIndicator";
    static props = {
        signStatus: { type: Object },
    };

    setup() {
        this.signStatus = this.props.signStatus;
    }

    async saveManually() {
        await this.signStatus.save();
    }

    async discardChanges() {
        await this.signStatus.discardChanges();
    }
}
