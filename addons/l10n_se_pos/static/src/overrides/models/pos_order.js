import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    useBlackBoxSweden() {
        return !!this.config.iface_sweden_fiscal_data_module;
    },
    getSpecificTax(category) {
        const tax = this.prices.taxDetails.subtotals[0].tax_groups.find(
            (tax) => tax.group_label === category
        );

        if (tax) {
            return tax.tax_amount;
        }

        return false;
    },
    waitForPushOrder() {
        var result = super.waitForPushOrder(...arguments);
        result = Boolean(this.useBlackBoxSweden() || result);
        return result;
    },
});
