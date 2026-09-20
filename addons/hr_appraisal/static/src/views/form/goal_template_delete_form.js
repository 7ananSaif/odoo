import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { addFieldDependencies, extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { GoalTemplateDeleteConfirmationDialog } from "@hr_appraisal/components/goal_template_delete_confirmation_dialog/goal_template_delete_confirmation_dialog";

export class AppraisalGoalDeleteFormController extends FormController {
    setup() {
        super.setup(...arguments);
        const { activeFields, fields } = extractFieldsFromArchInfo(
            this.archInfo,
            this.props.fields
        );
        addFieldDependencies(activeFields, fields, [
            { name: "child_ids", type:"one2many" }
        ]);
        this.orm = useService("orm");
        this.action = useService("action");
        this.deleteRecordsWithConfirmation = () => this.deleteRecursiveRecord();
    }
    async deleteRecursiveRecord() {
        this.dialogService.add(GoalTemplateDeleteConfirmationDialog, {
            hasChildren: this.model.root.data.child_ids.count > 0,
            confirm: async () => {
                await this.model.root.delete();
                this.env.config.historyBack();
            },
            confirmAll: async () => {
                await this.orm.call(this.model.root.resModel, "recursive_unlink", [this.model.root.resId]);
                this.env.config.historyBack();
            },
        });
    }
}

export const appraisalGoalDeleteFormView = {
    ...formView,
    Controller: AppraisalGoalDeleteFormController,
};

registry.category("views").add("appraisal_goal_delete_form", appraisalGoalDeleteFormView);
