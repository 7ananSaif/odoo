/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    waitForPushOrder() {
        return this.config_id.is_kenyan ? true : super.waitForPushOrder(...arguments);
    },
});
