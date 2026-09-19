import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

patch(OrderDisplay, {
    props: {
        ...OrderDisplay.props,
        orderAcceptTime: { type: Number, optional: true },
        orderPrepTime: { type: Number, optional: true },
    },
});

patch(OrderDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
        this.state = useState({ remainingTime: 0 });
        this.state.remainingTime = this._computeRemainingTime();
        this.interval = setInterval(() => {
            this.state.remainingTime = this._computeRemainingTime();
        }, 10000);
    },

    _computeRemainingTime() {
        if (this.showTimer) {
            const total_order_time =
                this.props.orderAcceptTime + this.props.orderPrepTime * 60 * 1000;
            return Math.max(
                0,
                Math.round((total_order_time - luxon.DateTime.now().ts) / (1000 * 60))
            );
        }
    },

    get showTimer() {
        return this.props.orderAcceptTime && this.order?.state !== "paid";
    },

    changePrepTime(order, increment) {
        order.prep_time = Math.max(0, order.prep_time + (increment ? 5 : -5));
    },

    onInputChangePrepTime(order, inputTime, event) {
        order.prep_time = Math.max(0, parseInt(inputTime || 0));
        event.target.value = order.prep_time;
    },
});
