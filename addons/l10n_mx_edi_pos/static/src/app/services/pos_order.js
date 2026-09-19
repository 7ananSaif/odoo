import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    // @Override
    setToInvoice(to_invoice) {
        if (this.company.country_id?.code === "MX" && !this.l10n_mx_edi_usage) {
            super.setToInvoice(false);
        } else {
            super.setToInvoice(to_invoice);
        }
    },
    // @Override
    serializeForORM() {
        const data = super.serializeForORM(...arguments);
        if (this.company.country_id?.code === "MX") {
            data.l10n_mx_edi_cfdi_to_public = this.l10n_mx_edi_cfdi_to_public;
        }
        return data;
    },
});
