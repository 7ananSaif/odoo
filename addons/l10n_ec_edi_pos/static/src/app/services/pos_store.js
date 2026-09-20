import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    // @Override
    async processServerData() {
        await super.processServerData();
        if (this.isEcuadorianCompany()) {
            this["l10n_latam.identification.type"] =
                this.models["l10n_latam.identification.type"].getFirst();
        }
    },
    isEcuadorianCompany() {
        return this.company.country_id?.code == "EC";
    },
    createNewOrder() {
        const order = super.createNewOrder(...arguments);
        if (!order.partner_id && this.isEcuadorianCompany()) {
            order.partner_id = this.config._final_consumer_id;
        }
        return order;
    },
    // @Override
    // For EC, if the partner on the refund was End Consumer we need to allow the user to change it.
    async selectPartner() {
        if (!this.isEcuadorianCompany()) {
            return super.selectPartner(...arguments);
        }
        const currentOrder = this.getOrder();
        if (!currentOrder) {
            return;
        }
        const currentPartner = currentOrder.getPartner();
        if (currentPartner && currentPartner.id === this.config._final_consumer_id) {
            this.dialog.add(PartnerList, {
                partner: currentPartner,
                getPayload: (newPartner) => currentOrder.setPartner(newPartner),
            });
            return currentPartner;
        }
        return super.selectPartner(...arguments);
    },
});

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(...arguments);
        if (this.company.country_id?.code == "EC") {
            this.to_invoice = true;
        }
    },
});
