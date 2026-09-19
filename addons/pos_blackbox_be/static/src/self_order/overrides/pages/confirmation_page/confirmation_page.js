import { patch } from "@web/core/utils/patch";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";
import { rpc } from "@web/core/network/rpc";

patch(ConfirmationPage.prototype, {
    beforePrintOrder() {
        if (this.selfOrder.config.iface_fiscal_data_module) {
            rpc(`/pos_blackbox_be/send_order/`, {
                access_token: this.selfOrder.access_token,
                order_access_token: this.props.orderAccessToken,
                order_id: this.confirmedOrder.id,
            });
            return false;
        }
        return super.beforePrintOrder();
    },

    get printOptions() {
        if (this.selfOrder.config.iface_fiscal_data_module) {
            return Object.assign(super.printOptions, { blackboxPrint: true });
        }
        return super.printOptions;
    },

    canPrintReceipt() {
        const result = super.canPrintReceipt();
        if (this.selfOrder.config.iface_fiscal_data_module) {
            return result && Boolean(this.confirmedOrder.blackbox_signature);
        }
        return result;
    },
});
