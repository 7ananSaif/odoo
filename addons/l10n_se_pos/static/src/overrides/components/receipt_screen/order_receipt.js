import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt.prototype, {
    get seType() {
        if (this.order.isReprint) {
            return "COPY";
        } else if (this.order.isProfo) {
            return "PRO FORMA";
        } else {
            return (this.order.amount_total < 0 ? "return" : "") + "receipt";
        }
    },
    get originalDate() {
        return deserializeDateTime(this.order.creation_date).toFormat("HH:mm dd/MM/yyyy");
    },
});
