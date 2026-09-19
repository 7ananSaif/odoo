import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

patch(PosOrderline.prototype, {
    isSettleDueLine() {
        const settleDueProduct = this.config.settle_due_product_id;
        return settleDueProduct && this.product_id.id === settleDueProduct.id;
    },
    isDepositLine() {
        const depositProduct = this.config.deposit_product_id;
        return depositProduct && this.product_id.id === depositProduct.id;
    },
    isSettleInvoiceLine() {
        const settleInvoiceProduct = this.config.settle_invoice_product_id;
        return settleInvoiceProduct && this.product_id.id === settleInvoiceProduct.id;
    },
    isAnySettleLine() {
        return this.isSettleDueLine() || this.isDepositLine() || this.isSettleInvoiceLine();
    },
    setFullProductName() {
        if (this.isSettleDueLine() && this.settled_order_id?.display_name) {
            this.full_product_name = this.settled_order_id.display_name;
        } else if (this.isSettleInvoiceLine() && this.settled_invoice_id?.name) {
            this.full_product_name = this.settled_invoice_id.name;
        } else {
            super.setFullProductName();
        }
    },
    get orderDisplayProductName() {
        if (this.isSettleDueLine() || this.isSettleInvoiceLine()) {
            return {
                name: this.full_product_name,
            };
        }
        return super.orderDisplayProductName;
    },
    get canBeRemoved() {
        return super.canBeRemoved && !this.isAnySettleLine();
    },
});
