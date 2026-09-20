import { Order } from "@pos_enterprise/app/components/order/order";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(Order.prototype, {
    /**
     * @override
     */
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.order_status = {
            placed: "Placed",
            acknowledged: "Acknowledged",
            food_ready: "Food Ready",
            dispatched: "Dispatched",
            completed: "Completed",
            cancelled: "Cancelled",
        };
    },

    /**
     * @override
     */
    async doneOrder() {
        super.doneOrder();
        if (this.order.pos_order_id.delivery_identifier) {
            await this.orm.call("pos.config", "order_status_update", [
                this.order.pos_order_id.raw.config_id,
                this.order.pos_order_id.id,
                "Food Ready",
                null,
                this.order.urban_piper_test,
            ]);
        }
    },

    _computeDuration() {
        if (this.order.pos_order_id.delivery_identifier) {
            const total_order_time = this.order.create_date
                .setZone("local")
                .plus({ minutes: this.order.pos_order_id.prep_time || 0 });
            return Math.max(
                Math.round((total_order_time.ts - luxon.DateTime.now().ts) / (1000 * 60)),
                0
            );
        }
        return super._computeDuration();
    },
});
