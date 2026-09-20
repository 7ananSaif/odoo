import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { TextInputPopup } from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        const result = await super.isOrderValid(...arguments);
        if (this.pos.isChileanCompany()) {
            if (!result) {
                return false;
            }
            if (
                this.order.isRefund &&
                this.order.getPartner().id === this.pos.config._consumidor_final_anonimo_id
            ) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Refund not possible"),
                    body: _t("You cannot refund orders for the Consumidor Final Anònimo."),
                });
                return false;
            }
            const mandatoryFacturaFields = [
                "l10n_cl_dte_email",
                "l10n_cl_activity_description",
                "street",
                "l10n_latam_identification_type_id",
                "l10n_cl_sii_taxpayer_type",
                "vat",
            ];
            const missingFields = [];
            const partner = this.order.getPartner();
            if (this.order.invoice_type == "factura" || this.order.isRefund) {
                for (const field of mandatoryFacturaFields) {
                    if (!partner[field]) {
                        missingFields.push(field);
                    }
                }
            }
            if (missingFields.length > 0) {
                this.pos.notification.add(
                    _t("Please fill out missing fields to proceed: " + missingFields.join(", "))
                );
                this.pos.editPartner(partner);
                return false;
            }
            return true;
        }
        return result;
    },
    shouldDownloadInvoice() {
        return this.pos.isChileanCompany() ? this.order.isFactura() : super.shouldDownloadInvoice();
    },
    async askBeforeValidation() {
        if (
            this.pos.isChileanCompany() &&
            this.order.payment_ids?.some((line) => line.payment_method_id.is_card_payment)
        ) {
            const voucherNumber = await makeAwaitable(this.pos.dialog, TextInputPopup, {
                rows: 4,
                title: _t("Please register the voucher number"),
            });
            if (!voucherNumber) {
                return;
            }
            this.order.voucher_number = voucherNumber;
        }
        return await super.askBeforeValidation();
    },
});
