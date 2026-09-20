import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    async afterOrderValidation(suggestToSync = false) {
        await super.afterOrderValidation(...arguments);
        const hasCustomerAccountAsPaymentMethod = this.order.payment_ids.find(
            (paymentline) => paymentline.payment_method_id.type === "pay_later"
        );
        const partner = this.order.getPartner();
        if (hasCustomerAccountAsPaymentMethod && partner.total_due !== undefined) {
            this.pos.refreshTotalDueOfPartner(partner);
        }
    },
});
