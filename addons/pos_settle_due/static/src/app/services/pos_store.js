import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.setAllTotalDueOfPartners(this.models["res.partner"].getAll());
    },
    getPartnerCredit(partner) {
        const order = this.getOrder();
        const partnerInfos = {
            totalDue: 0,
            posOrdersAmountDue: 0,
            invoicesAmountDue: 0,
            totalWithCart: order?.amount_total ?? 0,
            creditLimit: 0,
            useLimit: false,
            overDue: false,
        };

        if (!partner) {
            return partnerInfos;
        }
        if (partner.parent_name) {
            const parent = this.models["res.partner"].find((p) => p.name === partner.parent_name);
            if (parent) {
                partner = parent;
            }
        }

        partnerInfos.totalDue = this.currency.round(partner.total_due);
        partnerInfos.posOrdersAmountDue = this.currency.round(partner.pos_orders_amount_due);
        partnerInfos.invoicesAmountDue = this.currency.round(partner.invoices_amount_due);
        partnerInfos.remainingDue = this.currency.round(
            partnerInfos.totalDue - partnerInfos.posOrdersAmountDue - partnerInfos.invoicesAmountDue
        );
        partnerInfos.totalWithCart += partner.total_due || 0;
        partnerInfos.creditLimit = partner.credit_limit || 0;
        partnerInfos.overDue = partnerInfos.totalWithCart > partnerInfos.creditLimit;
        partnerInfos.useLimit =
            this.company.account_use_credit_limit &&
            partner.credit_limit > 0 &&
            partnerInfos.overDue;

        return partnerInfos;
    },
    async refreshTotalDueOfPartner(partner) {
        const res = await this.data.callRelated("res.partner", "get_total_due", [
            partner.id,
            this.config.id,
        ]);
        this.deviceSync.dispatch({ "res.partner": [partner] });
        const updatePartner = res["res.partner"][0];
        if (partner.parent_name) {
            const parent = this.models["res.partner"].find((p) => p.name === partner.parent_name);
            if (parent) {
                partner = parent;
            }
        }
        partner.total_due = updatePartner.total_due;
        partner.pos_orders_amount_due = updatePartner.pos_orders_amount_due;
        partner.invoices_amount_due = updatePartner.invoices_amount_due;
        return [updatePartner];
    },
    async setAllTotalDueOfPartners(partners) {
        const partners_total_due = await this.data.call("res.partner", "get_all_total_due", [
            partners.map((p) => p.id),
            this.config.id,
        ]);
        for (const partner of partners) {
            const updatedPartnerRecord = partners_total_due.find(
                (p) => p["res.partner"][0].id == [partner.id]
            );
            if (!updatedPartnerRecord) {
                // the partner has been deleted from the server
                partner.delete();
                continue;
            }
            const updatedPartner = updatedPartnerRecord["res.partner"][0];
            partner.total_due = updatedPartner.total_due;
            partner.pos_orders_amount_due = updatedPartner.pos_orders_amount_due;
            partner.invoices_amount_due = updatedPartner.invoices_amount_due;
        }
        return [partners];
    },
    async onClickSettleDue(orderIds, partnerId, commercialPartnerId) {
        const orders = await this.data.loadServerOrders([["id", "in", orderIds]]);
        const currentOrder = this.getOrder();
        currentOrder.commercialPartnerId = commercialPartnerId;
        currentOrder.setPartner(partnerId);
        for (const order of orders) {
            await this.addLineToCurrentOrder({
                price_unit: order.customer_due_total,
                qty: 1,
                taxes_id: [],
                product_tmpl_id: this.config.settle_due_product_id,
                settled_order_id: order,
            });
        }
    },
    async onClickSettleInvoices(invoiceIds, partnerId, commercialPartnerId) {
        const invoices = await this.data.read("account.move", invoiceIds);
        const currentOrder = this.getOrder();
        currentOrder.setPartner(partnerId);
        currentOrder.commercialPartnerId = commercialPartnerId;
        for (const invoice of invoices) {
            await this.addLineToCurrentOrder({
                price_unit: invoice.pos_amount_unsettled,
                qty: 1,
                taxes_id: [],
                product_tmpl_id: this.config.settle_invoice_product_id,
                settled_invoice_id: invoice,
            });
        }
    },
    async depositMoney(partner, amount = 0) {
        const paymentMethods = this.config.payment_method_ids.filter(
            (method) => method.type != "pay_later"
        );
        const selectionList = paymentMethods.map((paymentMethod) => ({
            id: paymentMethod.id,
            label: paymentMethod.name,
            item: paymentMethod,
        }));
        this.dialog.add(SelectionPopup, {
            title: _t("Select the payment method to deposit money"),
            list: selectionList,
            getPayload: async (selectedPaymentMethod) => {
                // Reuse an empty order that has no partner or has partner equal to the selected partner.
                let newOrder;
                const emptyOrder = this.getOpenOrders().find(
                    (order) =>
                        order.lines.length === 0 &&
                        order.payment_ids.length === 0 &&
                        (!order.partner || order.partner.id === partner.id)
                );
                if (emptyOrder) {
                    newOrder = emptyOrder;
                    // Set the empty order as the current order.
                    this.setOrder(newOrder);
                } else {
                    newOrder = this.addNewOrder();
                }
                const result = newOrder.addPaymentline(selectedPaymentMethod);
                if (!result.status) {
                    return false;
                }

                newOrder.is_settling_account = true;
                result.data.setAmount(amount);
                newOrder.setPartner(partner);
                newOrder.is_settling_account = true;
                this.navigate("PaymentScreen", {
                    orderUuid: this.selectedOrderUuid,
                    isDepositOrder: true,
                });
            },
        });
    },
});
