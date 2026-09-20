import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(PosStore.prototype, {
    useBlackBoxSweden() {
        return !!this.config.iface_sweden_fiscal_data_module;
    },
    hasNegativeAndPositiveProducts(product) {
        const isPositive = product.list_price >= 0;
        const order = this.getOrder();

        for (const id in order.getOrderlines()) {
            const line = order.getOrderlines()[id];
            if (
                (line.product_id.list_price >= 0 && !isPositive) ||
                (line.product_id.list_price < 0 && isPositive)
            ) {
                return true;
            }
        }
        return false;
    },
    async addLineToCurrentOrder(vals, opt = {}, configure = true) {
        const product = vals.product_tmpl_id;
        const productTaxesIds = product.taxes_id.map((tax) => tax.id);
        if (this.useBlackBoxSweden() && product.taxes_id.length === 0) {
            this.dialog.add(AlertDialog, {
                title: _t("POS error"),
                body: _t("Product has no tax associated with it."),
            });
            return;
        } else if (
            this.useBlackBoxSweden() &&
            !this.models["account.tax"]
                .filter((tax) => productTaxesIds.includes(tax.id))
                ?.every((tax) => tax.tax_group_id.pos_receipt_label)
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("POS error"),
                body: _t(
                    "Product has an invalid tax amount. Only 25%, 12%, 6% and 0% are allowed."
                ),
            });
            return;
        } else if (this.useBlackBoxSweden() && this.getOrder().lines.find((l) => l.is_return)) {
            this.dialog.add(AlertDialog, {
                title: _t("POS error"),
                body: _t("Cannot modify a refund order."),
            });
            return;
        } else if (this.useBlackBoxSweden() && this.hasNegativeAndPositiveProducts(product)) {
            this.dialog.add(AlertDialog, {
                title: _t("POS error"),
                body: _t("You can only make positive or negative order. You cannot mix both."),
            });
            return;
        } else {
            return await super.addLineToCurrentOrder(vals, opt, configure);
        }
    },
    async printReceipt({ order = this.getOrder() } = {}) {
        if (this.useBlackBoxSweden()) {
            if (order) {
                if (order.nb_print > 1) {
                    this.dialog.add(AlertDialog, {
                        title: _t("POS error"),
                        body: _t("A duplicate has already been printed once."),
                    });
                    return;
                }
                if (order.nb_print === 1) {
                    order.receipt_type = "kopia";
                    await this.pushSingleOrder(order);
                    order.receipt_type = false;
                    order.isReprint = true;
                }
                return super.printReceipt(...arguments);
            }
        } else {
            return super.printReceipt(...arguments);
        }
    },
});
