import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        if (this.pos.isEcuadorianCompany()) {
            if (
                this.order.isRefund &&
                this.order.getPartner().id === this.pos.config._final_consumer_id
            ) {
                this.dialog.add(AlertDialog, {
                    title: _t("Refund not possible"),
                    body: _t("You cannot refund orders for Consumidor Final."),
                });
                return false;
            }
        }
        return super.isOrderValid(...arguments);
    },
    shouldDownloadInvoice() {
        return this.pos.isEcuadorianCompany() ? false : super.shouldDownloadInvoice();
    },
});
