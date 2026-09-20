import { patch } from "@web/core/utils/patch";
import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";

patch(OrderDisplay, {
    props: {
        ...OrderDisplay.props,
        refreshAvatax: { type: Function, optional: true },
        isAvataxConfig: { type: Boolean, optional: true },
    },
});

patch(OrderDisplay.prototype, {
    async refreshAvatax() {
        if (!this.props.refreshAvatax) {
            return;
        }

        await this.props.refreshAvatax();
    },
});
