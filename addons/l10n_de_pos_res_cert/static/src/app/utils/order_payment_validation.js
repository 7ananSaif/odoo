import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    //@Override
    async finalizeValidation() {
        if (this.pos.isRestaurantCountryGermanyAndFiskaly()) {
            try {
                await this.pos.retrieveAndSendLineDifference(this.order);
            } catch {
                // do nothing with the error
            }
        }
        return await super.finalizeValidation(...arguments);
    },
});
