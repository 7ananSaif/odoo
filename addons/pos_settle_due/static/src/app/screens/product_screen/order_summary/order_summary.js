import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";

patch(OrderSummary.prototype, {
    _setValue(val) {
        const selectedLine = this.currentOrder.getSelectedOrderline();
        if (selectedLine?.isSettleDueLine() && val == "remove") {
            this.currentOrder.removeOrderline(selectedLine);
        }
        super._setValue(val);
    },
});
