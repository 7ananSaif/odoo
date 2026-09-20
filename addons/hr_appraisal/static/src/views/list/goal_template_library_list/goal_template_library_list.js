import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";

export class AppraisalGoalListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.defaultEmployeeId = this.props.context.default_employee_id;
    }
    async onSelect() {
        const records = this.model.root.selection.map((record) => record.resId);
        if (this.defaultEmployeeId){
            await this.orm.call(
                "hr.appraisal.goal",
                "generate_goals",
                [records],
                { context: { default_employee_id: this.defaultEmployeeId } }
            );
            await this.actionService.doAction({type: 'ir.actions.act_window_close'});
            await this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
        }
        else {
            // To open employees selection
            const action = await this.orm.call(
                "hr.appraisal.goal",
                "action_select_employees",
                [],
                { context: { goals_ids: records } }
            );
            return this.actionService.doAction(action);
        }
    }
    async onClose() {
        return this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }
}

export const appraisalGoalListView = {
    ...listView,
    buttonTemplate: 'hr_appraisal.AppraisalGoal.buttons',
    Controller: AppraisalGoalListController,
};

registry.category("views").add("goal_library_list", appraisalGoalListView);
