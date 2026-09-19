import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    tyroPaymentInProgress() {
        return this.payment_ids.some((paymentLine) => {
            if (
                paymentLine.payment_status &&
                paymentLine.payment_method_id.use_payment_terminal === "tyro"
            ) {
                return ["waitingCard", "waitingCancel"].includes(paymentLine.payment_status);
            } else {
                return false;
            }
        });
    },
});
