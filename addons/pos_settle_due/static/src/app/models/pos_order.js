import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    getSettleAmount() {
        return this.lines
            .filter((line) => line.isSettleDueLine() || line.isSettleInvoiceLine())
            .reduce((acc, line) => acc + line.prices.total_included, 0);
    },
});
