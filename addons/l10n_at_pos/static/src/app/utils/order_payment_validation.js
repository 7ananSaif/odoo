import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    async afterOrderValidation() {
        if (this.pos.config.company_id.l10n_at_is_fon_authenticated) {
            const [signed, receipt_number, qr_data] = await this.pos.data.call(
                "pos.order",
                "sign_order_receipt",
                [this.pos.selectedOrder.id]
            );
            // updating values after signing receipt for the selected order
            this.pos.selectedOrder.is_fiskaly_order_receipt_signed = signed;
            this.pos.selectedOrder.l10n_at_pos_order_receipt_qr_data = qr_data;
            this.pos.selectedOrder.l10n_at_pos_order_receipt_number = receipt_number;
        }
        await super.afterOrderValidation(...arguments);
    },
});
