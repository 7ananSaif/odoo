import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { BlackboxError } from "@pos_blackbox_be/pos/app/utils/blackbox_error";
import { ConnectionLostError } from "@web/core/network/rpc";
import { EMPTY_SIGNATURE } from "@pos_blackbox_be/pos/app/services/pos_store";

patch(OrderPaymentValidation.prototype, {
    async validateOrder(isForceValidate) {
        if (this.pos.useBlackBoxBe() && !this.pos.userSessionStatus) {
            this.pos.add(AlertDialog, {
                title: _t("POS error"),
                body: _t(
                    "The government's Fiscal Data Module requires every user to Clock In before " +
                        "sending an order.\n" +
                        "You can Clock In from the top-right menu (\u2261)."
                ),
            });
            return;
        }
        await super.validateOrder(isForceValidate);
    },
    async afterOrderValidation() {
        if (!this.order.blackbox_signature || this.order.blackbox_signature == EMPTY_SIGNATURE) {
            try {
                await this.pos.syncAllOrders({ orders: [this.currentOrder], throw: true });
            } catch (error) {
                if (error instanceof BlackboxError || error instanceof ConnectionLostError) {
                    this.currentOrder.state = "draft";
                    throw error;
                }
            }
        }
        return super.afterOrderValidation();
    },
    handleValidationError(error) {
        try {
            return super.handleValidationError(error);
        } catch (e) {
            if (e instanceof BlackboxError) {
                this.order.state = "draft";
                e.retry ??= this.finalizeValidation.bind(this);
            }
            throw error;
        }
    },
});
