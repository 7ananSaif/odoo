import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class HrEmployeeSelectionListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
    }
    async onSelect() {
        const records = this.model.root.selection.map((record) => record.resId);
        await this.orm.call(
            "hr.appraisal.goal",
            "generate_goals",
            [this.props.context.goals_ids, records],

        );
        await this.actionService.doAction({type: 'ir.actions.act_window_close'});
        await this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
    }
    async onClose() {
        return this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }
}

export const hrEmployeeSelectionListView = {
    ...listView,
    buttonTemplate: 'hr_appraisal.HrEmployeeSelection.buttons',
    Controller: HrEmployeeSelectionListController,
};

registry.category("views").add("hr_employee_selection_list", hrEmployeeSelectionListView);
