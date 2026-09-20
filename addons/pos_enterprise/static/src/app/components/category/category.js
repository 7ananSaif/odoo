import { Component } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";

export class Category extends Component {
    static template = "pos_enterprise.Category";
    static props = {
        category: Object,
    };

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.products = [];
        this.productCount = 0;
    }

    get shouldShowCategory() {
        const category = this.props.category;
        const selectedStageId = this.prepDisplay.selectedStageId;
        const products = {};

        this.productCount = 0;

        for (const state of category.states) {
            if (state.isStageDone(this.prepDisplay.lastStage.id)) {
                continue;
            }
            if (state.stage_id.id === selectedStageId || !selectedStageId) {
                const quantity = state.prep_line_id.quantity;
                const cancelled = state.prep_line_id.cancelled;

                if (!products[state.product.id]) {
                    products[state.product.id] = {
                        id: state.product.id,
                        name: state.prep_line_id.product_id.display_name,
                        categoryIds: state.categories.map((categ) => categ.id),
                        quantity: quantity,
                        cancelled: cancelled,
                    };
                } else {
                    products[state.product.id].quantity += quantity;
                    products[state.product.id].cancelled += cancelled;
                }

                this.productCount += state.prep_line_id.quantity - state.prep_line_id.cancelled;
            }
            if (
                !products[state.product.id] &&
                this.prepDisplay.selectedProductIds.has(state.product.id)
            ) {
                products[state.product.id] = {
                    id: state.product.id,
                    name: state.prep_line_id.product_id.display_name,
                    categoryIds: state.categories.map((categ) => categ.id),
                    quantity: 0,
                    cancelled: 0,
                };
            }
        }

        this.products = Object.values(products).sort((a, b) => b.quantity - a.quantity);
        return this.products.length;
    }
}
