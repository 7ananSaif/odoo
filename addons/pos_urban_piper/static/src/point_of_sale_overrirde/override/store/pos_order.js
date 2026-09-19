import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.isDeliveryRefundOrder = false;
    },

    initState() {
        super.initState();
        this.uiState = {
            ...this.uiState,
            orderAcceptTime: 0,
        };
    },

    getDeliveryProviderName() {
        return this.delivery_provider_id ? this.delivery_provider_id.name : "";
    },

    getOrderStatus() {
        return this.delivery_status ? this.delivery_status : "";
    },

    get isDirectSale() {
        return Boolean(super.isDirectSale && !this.delivery_identifier);
    },

    get deliveryOrderType() {
        const deliveryJson = JSON.parse(this?.delivery_json || "{}");
        return deliveryJson?.order?.details?.ext_platforms?.[0]?.delivery_type;
    },

    isFutureOrder() {
        return false;
    },
    get getProviderOrderId() {
        return JSON.parse(this.delivery_json || "{}").order?.details?.ext_platforms?.[0].id || "";
    },
});
