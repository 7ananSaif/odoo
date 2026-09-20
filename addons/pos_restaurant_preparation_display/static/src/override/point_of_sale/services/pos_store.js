import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async restoreOrdersToOriginalTable(order, unmergeTable) {
        const newOrder = await super.restoreOrdersToOriginalTable(...arguments);

        if (newOrder) {
            await this.data.call("pos.prep.order", "unmerge_orders", [
                newOrder.uiState.mappingOrderlinesUuid,
                newOrder.id,
            ]);
            newOrder.uiState.mappingOrderlinesUuid = {};
        }
        return newOrder;
    },

    async handleFailToPrepareOrderTransfer(orders) {
        await super.handleFailToPrepareOrderTransfer(...arguments);

        const ids = orders.filter((order) => typeof order.id === "number").map((order) => order.id);
        await this.data.call("pos.prep.order", "notify_pdis", [ids]);
    },

    async mergeOrders(sourceOrder, destOrder) {
        const result = await super.mergeOrders(...arguments);
        await this.data.call("pos.prep.order", "merge_orders", [sourceOrder.id, result.id]);

        return result;
    },
});
