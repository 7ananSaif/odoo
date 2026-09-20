import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt.prototype, {
    get isTyroMerchantReceipt() {
        return this.paymentLines.some((line) => line.tyroMerchantReceipt);
    },
});
