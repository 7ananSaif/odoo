import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { GoalTemplateDeleteConfirmationDialog } from "@hr_appraisal/components/goal_template_delete_confirmation_dialog/goal_template_delete_confirmation_dialog";

export class AppraisalGoalDeleteListController extends ListController {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.action = useService("action");
        this.deleteRecordsWithConfirmation = () => this.deleteRecursiveRecord();
    }
    async deleteRecursiveRecord() {
        this.dialogService.add(GoalTemplateDeleteConfirmationDialog, {
            hasChildren: this.model.root.selection.some((record) => record.data.child_ids.count > 0),
            confirm: async () => {
                await this.model.root.deleteRecords(this.model.root.selection);
            },
            confirmAll: async () => {
                await this.orm.call(this.model.root.resModel, "recursive_unlink", [
                    this.model.root.selection.map((r) => r.resId)
                ]);
                await this.action.doAction({
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                });
            },
        });
    }
}

export const appraisalGoalDeleteListView = {
    ...listView,
    Controller: AppraisalGoalDeleteListController,
};

registry.category("views").add("appraisal_goal_delete_list", appraisalGoalDeleteListView);
