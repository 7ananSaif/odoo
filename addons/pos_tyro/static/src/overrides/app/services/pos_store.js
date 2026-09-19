import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async addTyroSurcharge(amount, surchargeProduct) {
        const currentOrder = this.getOrder();
        const line = currentOrder.lines.find((line) => line.product_id.id === surchargeProduct.id);

        if (line) {
            line.setUnitPrice(amount + line.price_unit);
        } else {
            await this.addLineToCurrentOrder({
                product_id: surchargeProduct,
                price_unit: amount,
                product_tmpl_id: surchargeProduct.product_tmpl_id,
            });
        }
    },

    async onDeleteOrder(order) {
        if (order.amountPaid > 0) {
            this.dialog.add(AlertDialog, {
                title: _t("Cannot cancel order"),
                body: _t(
                    "This order has one or more completed payments, please refund them before cancelling."
                ),
            });
            return false;
        }
        return super.onDeleteOrder(...arguments);
    },

    onClickBackButton() {
        if (this.getOrder()?.tyroPaymentInProgress()) {
            this.dialog.add(AlertDialog, {
                title: _t("Payment in progress"),
                body: _t("Please complete or cancel the payment before navigatating away."),
            });
        } else {
            return super.onClickBackButton(...arguments);
        }
    },
});
