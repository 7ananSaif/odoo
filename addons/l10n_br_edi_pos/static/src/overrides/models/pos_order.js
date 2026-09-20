import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { qrCodeSrc } from "@point_of_sale/utils";

patch(PosOrder.prototype, {
    l10nBrEdiGetNrUniqueItems() {
        // As specified by DANFE NFC-e (Documento Auxiliar da Nota Fiscal Eletrônica):
        // The total count of distinct items (products or services) listed in the NFC-e. This refers to
        // the number of unique items, not the sum of their quantities.
        const unique_products = new Set(this.getOrderlines().map((line) => line.product_id));
        return unique_products.size;
    },

    l10nBrEdiGetFormattedAccessKey() {
        // Split into groups of 4, separated by a space:
        // 41250149233848000150550010000008271543438478 ->
        // 4125 0149 2338 4800 0150 5500 1000 0008 2715 4343 8478
        const key = this.l10n_br_access_key;
        if (!key) {
            return "";
        }
        return key.match(/.{4}/g)?.join(" ") || "";
    },

    l10nBrEdiGetNFCeQRSrc() {
        if (this.l10n_br_edi_avatax_data && this.l10n_br_edi_avatax_data["header"]) {
            return qrCodeSrc(this.l10n_br_edi_avatax_data["header"]["goods"]["nfceQrCode"]);
        }
    },

    // @override
    setToInvoice(to_invoice) {
        if (this.company.account_fiscal_country_id?.code === "BR") {
            super.setToInvoice(false);
        } else {
            super.setToInvoice(to_invoice);
        }
    },
});
