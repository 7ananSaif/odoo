import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    actionOpenSaleOrders() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            target: "current",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            context: {
                search_default_partner_id: this.statementLineData.partner_id.id,
            },
        });
    },

    get isSalesButtonShown() {
        // This is a temporary solution
        // Should be fixed later by task 5241035
        return !!this.statementLineData.partner_id.id;
    },

    get buttons() {
        const buttonsToDisplay = super.buttons;
        if (this.isSalesButtonShown) {
            buttonsToDisplay.sale = {
                label: _t("Sales"),
                action: this.actionOpenSaleOrders.bind(this),
                classes: "sales-btn",
            };
        }
        return buttonsToDisplay;
    },
});
