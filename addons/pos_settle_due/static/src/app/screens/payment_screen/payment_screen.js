import { _t } from "@web/core/l10n/translation";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(PaymentScreen, {
    props: {
        ...PaymentScreen.props,
        isDepositOrder: { type: Boolean, optional: true },
    },
});

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const order = this.currentOrder;
        const settleLines = order.lines.filter(
            (line) => line.isSettleDueLine() || line.isSettleInvoiceLine()
        );
        if (settleLines.length || this.props.isDepositOrder) {
            this.payment_methods_from_config = this.payment_methods_from_config.filter(
                (pm) => pm.type !== "pay_later"
            );
        }
    },
    toggleIsToInvoice() {
        if (
            !this.currentOrder.isToInvoice() &&
            this.currentOrder.is_settling_account &&
            this.currentOrder.lines.length === 0
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Empty Order"),
                body: _t("Empty orders cannot be invoiced."),
            });
        } else {
            super.toggleIsToInvoice();
        }
    },
    get partnerInfos() {
        const order = this.currentOrder;
        return this.pos.getPartnerCredit(order.getPartner());
    },
    get highlightPartnerBtn() {
        const order = this.currentOrder;
        const partner = order.getPartner();
        return (!this.partnerInfos.useLimit && partner) || (!this.partnerInfos.overDue && partner);
    },
    async ensurePartnerSelected(order) {
        let partner = order.getPartner();
        if (!partner) {
            const confirmed = await ask(this.dialog, {
                title: _t("The order is empty"),
                body: _t(
                    "Do you want to deposit money to a specific customer? If so, first select him/her."
                ),
                confirmLabel: _t("Yes"),
            });
            if (!(confirmed && (partner = await this.pos.selectPartner()))) {
                return false;
            }
        }
        return partner;
    },
    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const change = -order.change;
        const settleLines = order.lines.filter(
            (line) => line.isSettleDueLine() || line.isSettleInvoiceLine()
        );
        const paylaterPaymentMethod = this.pos.models["pos.payment.method"].find(
            (pm) =>
                this.pos.config.payment_method_ids.some((m) => m.id === pm.id) &&
                pm.type === "pay_later"
        );
        const existingPayLaterPayment = order.payment_ids.find(
            (payment) => payment.payment_method_id.type == "pay_later"
        );

        // If the user attempts to deposit a zero amount
        if (this.props.isDepositOrder && this.pos.currency.isZero(change) && order.isEmpty()) {
            return this.dialog.add(AlertDialog, {
                title: _t("The order is empty"),
                body: _t("You can not deposit zero amount."),
            });
        }

        //If it's a deposit or settle due order
        if (
            ((!this.pos.currency.isZero(change) &&
                order.getOrderlines().length === 0 &&
                this.props.isDepositOrder) ||
                settleLines.length) &&
            paylaterPaymentMethod &&
            !existingPayLaterPayment
        ) {
            if (order.isRefund) {
                return this.dialog.add(AlertDialog, {
                    title: _t("Error"),
                    body: _t("You cannot refund a deposit/settling order."),
                });
            }
            const partner = await this.ensurePartnerSelected(order);
            if (!partner) {
                return;
            }
            if (settleLines.length) {
                return this.settleOrderDues(order, partner, paylaterPaymentMethod, settleLines);
            } else {
                return this.depositOrder(order, partner, change, paylaterPaymentMethod);
            }
        } else {
            return super.validateOrder(...arguments);
        }
    },
    async settleOrderDues(order, partner, paylaterPaymentMethod, settleLines) {
        const commercialPartnerId = order.commercialPartnerId;
        const amountToSettle = order.getSettleAmount();
        if (commercialPartnerId && commercialPartnerId == partner.commercial_partner_id.id) {
            const confirmed = await ask(this.dialog, {
                title: _t("Settle due orderlines"),
                body: _t(
                    "Do you want to deposit %s to %s?",
                    this.env.utils.formatCurrency(amountToSettle),
                    partner.name
                ),
                confirmLabel: _t("Yes"),
            });
            if (confirmed) {
                const result = order.addPaymentline(paylaterPaymentMethod);
                if (!result.status) {
                    return false;
                }

                result.data.setAmount(-amountToSettle);
                settleLines.forEach((line) => (line.qty = 0));
                return super.validateOrder(...arguments);
            }
        } else {
            this.dialog.add(AlertDialog, {
                title: _t("Error"),
                body: _t(
                    "The selected customer is not in the list of partners of the ongoing settling orderlines."
                ),
            });
        }
    },
    async depositOrder(order, partner, change, paylaterPaymentMethod) {
        const confirmed = await ask(this.dialog, {
            title: _t("The order is empty"),
            body: _t(
                "Do you want to deposit %s to %s?",
                this.env.utils.formatCurrency(change),
                partner.name
            ),
            confirmLabel: _t("Yes"),
        });
        if (confirmed) {
            await this.pos.addLineToCurrentOrder({
                price_unit: change,
                qty: 1,
                taxes_id: [],
                product_tmpl_id: this.pos.config.deposit_product_id,
            });
            const result = order.addPaymentline(paylaterPaymentMethod);
            if (!result.status) {
                return false;
            }

            result.data.setAmount(-change);
            const depositLines = order.lines.filter((l) => l.isDepositLine());
            depositLines.forEach((line) => (line.qty = 0));
            return super.validateOrder(...arguments);
        }
    },
    getLineToRemove() {
        return this.currentOrder.lines.filter(
            (line) =>
                line.product_id.uom_id.isZero(line.qty) &&
                !line.isSettleDueLine() &&
                !line.isSettleInvoiceLine()
        );
    },
});
