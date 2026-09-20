/* global Sha1 */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    useBlackBoxBe() {
        return Boolean(this.config.iface_fiscal_data_module);
    },
    getTaxAmountByPercent(tax_percentage, lines = false) {
        if (!lines) {
            lines = this.getOrderlines();
        }
        const taxDetails = lines.map((l) => l.prices);
        const matches = taxDetails
            .flatMap((td) => td.taxes_data)
            .filter((t) => t.tax.amount_type === "percent" && t.tax.amount === tax_percentage);
        const tax = matches.reduce((acc, match) => acc + match.tax_amount, 0);

        return tax ? tax : false;
    },
    waitForPushOrder() {
        const result = super.waitForPushOrder();
        return Boolean(this.useBlackBoxBe() || result);
    },
    getPlu(lines = null) {
        if (lines === null) {
            lines = this.lines;
        }
        let order_str = "";
        lines.forEach((line) => (order_str += line.generatePluLine()));
        const sha1 = Sha1.hash(order_str);
        return sha1.slice(sha1.length - 8);
    },
    updateReceiptType() {
        const order_total_with_tax = this.priceIncl;
        const sale = this.state == "paid" ? "NS" : "PS";
        const refund = this.state == "paid" ? "NR" : "PR";
        if (order_total_with_tax > 0) {
            this.uiState.receipt_type = sale;
        } else if (order_total_with_tax < 0) {
            this.uiState.receipt_type = refund;
        } else {
            if (this.lines.length > 0 && this.lines[0].getQuantity() < 0) {
                this.uiState.receipt_type = refund;
            } else {
                this.uiState.receipt_type = sale;
            }
        }
    },
    setDataForPushOrderFromBlackbox(data) {
        if (!this.uiState.receipt_type) {
            this.updateReceiptType();
        }
        this.blackbox_signature = data.signature;
        this.blackbox_unit_id = data.vsc;
        this.plu_hash = this.getPlu();
        this.blackbox_vsc_identification_number = data.vsc;
        this.blackbox_unique_fdm_production_number = data.fdm_number;
        this.blackbox_ticket_counters =
            this.uiState.receipt_type + " " + data.ticket_counter + "/" + data.total_ticket_counter;
        this.blackbox_time = data.time.replace(/(\d{2})(\d{2})(\d{2})/g, "$1:$2:$3");
        this.blackbox_date = data.date.replace(/(\d{4})(\d{2})(\d{2})/g, "$3-$2-$1");
    },
    getBlackboxData() {
        return {
            blackbox_signature: this.blackbox_signature,
            plu_hash: this.plu_hash,
            blackbox_vsc_identification_number: this.blackbox_vsc_identification_number,
            blackbox_unique_fdm_production_number: this.blackbox_unique_fdm_production_number,
            blackbox_ticket_counters: this.blackbox_ticket_counters,
            blackbox_time: this.blackbox_time,
            blackbox_date: this.blackbox_date,
        };
    },
});
