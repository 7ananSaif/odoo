import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons();
        const orderline = this.currentOrder.getSelectedOrderline();
        if (orderline?.isSettleDueLine() || orderline?.isSettleInvoiceLine()) {
            this.pos.numpadMode = "price";
            buttons.forEach((button) => {
                if (
                    button.value === "quantity" ||
                    button.value === "discount" ||
                    button.value === "-"
                ) {
                    button.disabled = true;
                }
            });
        }
        return buttons;
    },
});
