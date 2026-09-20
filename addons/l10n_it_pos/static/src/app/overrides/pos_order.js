import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    _convertToDDMMYYYY(date) {
        const [day, month, year] = date.split("/");
        return `${day.padStart(2, "0")}${month.padStart(2, "0")}${year}`;
    },

    get isRefunded() {
        return this.lines.every((line) => line.qty < 0);
    },
});
