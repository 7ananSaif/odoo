import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

class CardReceiveTermsViewDialog extends Component {
    static template = "hr_expense_stripe.cardReceiveTermsViewDialog";
    static components = { Dialog };

    static props = {
        action: Object,
        close: Function,
    };
}

export function CardReceiveTermsAction(env, action) {
    env.services.dialog.add(CardReceiveTermsViewDialog, { action });
}

registry.category("actions").add("hr_expense_stripe.expense_stripe_card_receive_terms", CardReceiveTermsAction);
