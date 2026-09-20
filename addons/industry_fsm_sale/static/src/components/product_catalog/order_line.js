import { onWillStart } from "@odoo/owl";

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";

patch(ProductCatalogOrderLine.prototype, {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.isSalesman = true;
        onWillStart(async () => {
            if (this.env.fsm_task_id) {
                this.isSalesman = await user.hasGroup("sales_team.group_sale_salesman");
            }
        });
    },

    get showPrice() {
        let showPrice = super.showPrice;
        if (this.env.fsm_task_id) {
            showPrice = showPrice && this.isSalesman;
        }
        return showPrice;
    }
})
