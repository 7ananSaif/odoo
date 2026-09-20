import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { qrCodeSrc } from "@point_of_sale/utils";

patch(OrderPaymentValidation.prototype, {
    async beforePostPushOrderResolve(order, order_server_ids) {
        if (this.pos.config.is_kenyan) {
            this.pos.env.services.ui.block();
            try {
                await this.pos.data.call("pos.order", "action_post_order", [order_server_ids], {});
            } catch (error) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Error"),
                    body: _t(error.data.message),
                });
            } finally {
                const l10n_ke_edi_oscu_pos_data = await this.pos.data.call(
                    "pos.order",
                    "get_l10n_ke_edi_oscu_pos_data",
                    [order_server_ids],
                    {}
                );

                order.l10n_ke_edi_oscu_pos_qrsrc =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_qrurl
                        ? qrCodeSrc(l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_qrurl)
                        : undefined;

                order.l10n_ke_edi_oscu_pos_date =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_date;
                order.l10n_ke_edi_oscu_pos_receipt_number =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_receipt_number;
                order.l10n_ke_edi_oscu_pos_internal_data =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_internal_data;
                order.l10n_ke_edi_oscu_pos_signature =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_signature;
                order.l10n_ke_edi_oscu_pos_order_json =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_order_json;
                order.l10n_ke_edi_oscu_pos_serial_number =
                    l10n_ke_edi_oscu_pos_data.l10n_ke_edi_oscu_pos_serial_number;

                this.pos.env.services.ui.unblock();
            }
        }

        return super.beforePostPushOrderResolve(...arguments);
    },

    shouldDownloadInvoice() {
        return this.pos.config.is_kenyan ? false : super.shouldDownloadInvoice();
    },

    async askBeforeValidation() {
        if (this.pos.config.is_kenyan) {
            let errorMessage = "";
            const unregisteredProducts = this.order.lines.filter(
                (line) => !line.product_id.checkEtimsFields()
            );

            if (unregisteredProducts.length > 0) {
                errorMessage += _t(
                    "All product have to be registered to eTIMS, you can register them in the product view.\n"
                );
            }

            if (
                ![0, this.order.lines.length].includes(
                    this.order.lines.filter((line) => line.refunded_orderline_id !== undefined)
                        .length
                )
            ) {
                errorMessage += _t("You can't mix refund lines and order lines.\n");
            }

            if (errorMessage) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("Error"),
                    body: _t(errorMessage),
                });
                return false;
            }
        }
        return await super.askBeforeValidation();
    },
});
