import { Component } from "@odoo/owl";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { computeFontColor } from "@pos_enterprise/app/utils/utils";

export class Stages extends Component {
    static template = "pos_enterprise.Stages";
    static props = {
        stages: Object,
    };

    setup() {
        this.prepDisplay = usePrepDisplay();
    }

    getFontColor(bgColor) {
        return computeFontColor(bgColor);
    }

    orderCount(stageId) {
        const prepOrderIds = this.prepDisplay.data.models["pos.prep.state"]
            .getAll()
            .reduce((prepOrders, state) => {
                if (state.stage_id.id === stageId && this.prepDisplay.checkStateVisibility(state)) {
                    prepOrders.add(state.prep_line_id.prep_order_id.id);
                }
                return prepOrders;
            }, new Set());
        return prepOrderIds.size;
    }
}
