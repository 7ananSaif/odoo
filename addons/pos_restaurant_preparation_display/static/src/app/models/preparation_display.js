import { patch } from "@web/core/utils/patch";
import { PrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";

patch(PrepDisplay.prototype, {
    async setup() {
        await super.setup(...arguments);
    },
    get tables() {
        const result = {};
        for (const order of this.filteredOrders) {
            if (order.prepOrder.pos_order_id.table_id) {
                if (!result[order.prepOrder.pos_order_id.table_id?.id]) {
                    result[order.prepOrder.pos_order_id.table_id.id] = [];
                }
                result[order.prepOrder.pos_order_id.table_id.id].push(order.stage.id);
            }
        }
        return result;
    },
});
