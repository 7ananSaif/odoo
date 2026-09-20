import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(OrderPaymentValidation.prototype, {
    //@override
    async validateOrder(isForceValidate) {
        if (this.pos.isCountryGermanyAndFiskaly() && !this.pos.data.network.offline) {
            if (this.pos.validateOrderFree) {
                this.pos.validateOrderFree = false;
                try {
                    await super.validateOrder(...arguments);
                } finally {
                    this.pos.validateOrderFree = true;
                }
            }
        } else {
            await super.validateOrder(...arguments);
        }
    },
    //@override
    async finalizeValidation() {
        if (this.pos.isCountryGermanyAndFiskaly() && !this.pos.data.network.offline) {
            if (
                this.order.isTransactionInactive() &&
                !this.order.uiState.networkError &&
                !this.order.uiState.fiskalyServerError
            ) {
                try {
                    this.pos.ui.block();
                    await this.pos.createTransaction(this.order);
                } catch (error) {
                    if (error.status === 0) {
                        this.pos.showFiskalyNoInternetConfirmPopup(this);
                    } else {
                        const message = {
                            unknown: _t("An unknown error has occurred! Please, contact Odoo."),
                        };
                        this.pos.fiskalyError(error, message);
                    }
                } finally {
                    this.pos.ui.unblock();
                }
            }
            if (
                this.order.isTransactionStarted() &&
                !this.order.uiState.fiskalyServerError &&
                !this.order.uiState.networkError
            ) {
                try {
                    this.pos.ui.block();
                    await this.pos.finishShortTransaction(this.order);
                    return await super.finalizeValidation(...arguments);
                } catch (error) {
                    if (error.status === 0) {
                        this.pos.showFiskalyNoInternetConfirmPopup(this);
                    } else {
                        const message = {
                            unknown: _t("An unknown error has occurred! Please, contact Odoo."),
                        };
                        this.pos.fiskalyError(error, message);
                    }
                } finally {
                    this.pos.ui.unblock();
                }
            } else if (
                this.order.isTransactionFinished() ||
                this.order.uiState.fiskalyServerError
            ) {
                return await super.finalizeValidation(...arguments);
            }
        } else {
            return await super.finalizeValidation(...arguments);
        }
    },
});
