import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

class IssuingTermsViewDialog extends Component {
    static template = "hr_expense_stripe.issuingTermsViewDialog";
    static components = { Dialog };

    static props = {
        action: Object,
        close: Function
    };

    setup() {
        this.close = this.props.close;
    }
}

export function IssuingTermsAction(env, action) {
    return new Promise((resolve) => {
        env.services.dialog.add(
            IssuingTermsViewDialog,
            {
                action
            },
            {
                onClose: () => {
                    resolve({ type: "ir.actions.act_window_close" });
                },
            }
        );
    });
}

registry.category("actions").add("hr_expense_stripe.expense_stripe_issuing_terms", IssuingTermsAction);
