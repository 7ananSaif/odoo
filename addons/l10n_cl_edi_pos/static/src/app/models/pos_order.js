import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        if (this.isChileanCompany()) {
            this.to_invoice = vals.to_invoice === false ? vals.to_invoice : true;
            this.invoice_type = vals.invoice_type || "boleta";
            this.voucher_number = vals.voucher_number || "";
        }
    },
    isChileanCompany() {
        return this.company.country_id?.code == "CL";
    },
    isToInvoice() {
        if (this.isChileanCompany()) {
            return true;
        }
        return super.isToInvoice(...arguments);
    },
    setToInvoice(to_invoice) {
        if (this.isChileanCompany()) {
            this.assertEditable();
            this.to_invoice = true;
        } else {
            super.setToInvoice(...arguments);
        }
    },
    isFactura() {
        if (this.invoice_type == "boleta") {
            return false;
        }
        return true;
    },
});
