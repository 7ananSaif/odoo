import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BankRecButton extends Component {
    static template = "account_accountant.BankRecButton";
    static props = {
        label: { type: String, optional: true },
        action: { type: Function, optional: true },
        count: { type: [Number, { value: null }], optional: true },
        primary: { type: Boolean, optional: true },
        toReview: { type: Boolean, optional: true },
        classes: { type: String, optional: true },
    };
    static defaultProps = {
        primary: false,
        classes: "",
    };

    setup() {
        this.ui = useService("ui");
    }
}
