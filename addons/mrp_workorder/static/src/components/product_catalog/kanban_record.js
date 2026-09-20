import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { patch } from "@web/core/utils/patch";
import { KanbanRecord } from "@web/views/kanban/kanban_record";

patch(ProductCatalogKanbanRecord.prototype, {
    _getUpdateQuantityAndGetPriceParams() {
        const params = {
            ...super._getUpdateQuantityAndGetPriceParams(),
            from_shop_floor: this.props.record.context.from_shop_floor,
        };
        if ("workorder_id" in this.props.record.context) {
            params.workorder_id = this.props.record.context.workorder_id;
        }
        return params;
    },

    _updateQuantity() {
        const result = super._updateQuantity();
        this.props.pushCatalogKanbanUpdate?.(result);
    },
});

patch(ProductCatalogKanbanRecord, {
    props: [...KanbanRecord.props, "pushCatalogKanbanUpdate?"],
});
