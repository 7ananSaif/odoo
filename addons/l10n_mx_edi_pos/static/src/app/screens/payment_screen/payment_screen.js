import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.isMxEdiPopupOpen = false;
    },
    //@override
    async toggleIsToInvoice() {
        if (this.pos.company.country_id?.code === "MX" && !this.currentOrder.isToInvoice()) {
            const addedMxFields = await this.pos.addL10nMxEdiFields(this.currentOrder);
            if (!addedMxFields) {
                this.currentOrder.setToInvoice(!this.currentOrder.isToInvoice());
            }
        }
        await super.toggleIsToInvoice(...arguments);
    },
    areMxFieldsVisible() {
        return this.pos.company.country_id?.code === "MX" && this.currentOrder.isToInvoice();
    },
});
