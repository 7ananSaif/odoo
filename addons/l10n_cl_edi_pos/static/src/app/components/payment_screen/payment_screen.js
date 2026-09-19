import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async toggleIsToInvoice() {
        if (this.pos.isChileanCompany()) {
            if (this.currentOrder.invoice_type == "boleta") {
                this.currentOrder.invoice_type = "factura";
            } else {
                this.currentOrder.invoice_type = "boleta";
            }
            this.render(true);
        } else {
            await super.toggleIsToInvoice(...arguments);
        }
    },
    highlightInvoiceButton() {
        if (this.pos.isChileanCompany()) {
            return this.currentOrder.isFactura();
        }
        return this.currentOrder.isToInvoice();
    },
});
