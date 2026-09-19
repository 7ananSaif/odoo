import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useInactivity } from "../use_inactivity";

export class EndPage extends Component {
    static template = "frontdesk.EndPage";
    static props = {
        hostData: { optional: true },
        isDrinkSelected: Boolean,
        isMobile: Boolean,
        onClose: Function,
        plannedVisitorData: { optional: true },
        showScreen: Function,
        theme: String,
    };
    setup() {
        if (!this.props.isMobile) {
            useInactivity(() => this.props.onClose(), 15000);
        }
    }
}

registry.category("frontdesk_screens").add("EndPage", EndPage);
