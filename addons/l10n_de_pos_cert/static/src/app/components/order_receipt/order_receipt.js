import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt.prototype, {
    get originalDate() {
        return deserializeDateTime(this.order.creation_date).toFormat("HH:mm dd/MM/yyyy");
    },
});
