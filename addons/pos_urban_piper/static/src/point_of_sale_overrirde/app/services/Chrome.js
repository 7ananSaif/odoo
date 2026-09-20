import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos.data.connectWebSocket("DELIVERY_ORDER_COUNT", async (order_id) => {
            await this.pos._fetchUrbanpiperOrderCount(order_id);
        });
        this.pos.data.connectWebSocket("STORE_ACTION", async (data) => {
            await this.pos._fetchStoreAction(data);
        });
    },
});
