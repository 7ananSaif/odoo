import { Order } from "@pos_enterprise/app/components/order/order";
import { patch } from "@web/core/utils/patch";
import { getTime } from "@pos_urban_piper/utils";

patch(Order.prototype, {
    get deliveryDatetime() {
        return getTime(this.order.delivery_datetime);
    },
});
