import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";

export class EsgCarbonEmissionListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
    }

    async createRecord() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "esg.other.emission",
            views: [[false, "form"]],
            target: "current",
        });
    }
}
