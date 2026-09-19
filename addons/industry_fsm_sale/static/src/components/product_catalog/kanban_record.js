import { useSubEnv } from "@odoo/owl";
import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { rpc } from "@web/core/network/rpc";
import { useService } from '@web/core/utils/hooks';

export class FSMProductCatalogKanbanRecord extends ProductCatalogKanbanRecord {
    setup() {
        super.setup();
        this.orm = useService('orm');
        useSubEnv({
            ...this.env,
            fsm_task_id: this.props.record.context.fsm_task_id,
            resetQuantity: this.debouncedUpdateQuantity.bind(this),
        });
    }

    async _updateQuantity() {
        const { action, price, min_quantity } = await rpc("/product/catalog/update_order_line_info", {
            order_id: this.env.orderId,
            product_id: this.env.productId,
            quantity: this.productCatalogData.quantity,
            res_model: this.env.orderResModel,
            task_id: this.env.fsm_task_id,
            child_field: this.env.childField,
            section_id: this.env.selectedSectionId,
        });
        if (price) {
            this.productCatalogData.price = parseFloat(price);
        }
        if (min_quantity) {
            this.productCatalogData.minimumQuantityOnProduct = min_quantity;
        }
        if (action && action !== true) {
            const actionContext = {
                'default_product_id': this.props.record.data.id,
            };
            const options = {
                additionalContext: actionContext,
                onClose: async (closeInfo) => {
                    const domain = [
                        ['task_id', '=', this.env.fsm_task_id],
                        ['product_id', '=', this.env.productId],
                        ['product_uom_qty', '>', 0],
                    ];
                    let lines = await this.orm.searchRead(
                        'sale.order.line',
                        domain,
                        ['product_uom_qty', 'parent_id'],
                    );
                    if (this.env.orderId) {
                        lines = lines.filter(
                            (line) => this.env.searchModel.selectedSection.sectionId ?
                                line.parent_id?.[0] == this.env.searchModel.selectedSection.sectionId : line.parent_id == false
                        );
                    }
                    const quantity = lines.reduce(
                        (total, line) => total + line.product_uom_qty, 0
                    );
                    this.notifyLineCountChange(quantity - this.productCatalogData.quantity);
                    this.productCatalogData.quantity = quantity;
                    this.productCatalogData.tracking = true;
                },
            };
            await this.action.doAction(action, options);
        }
    }
};
