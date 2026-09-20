import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { progressBarField, ProgressBarField } from "@web/views/fields/progress_bar/progress_bar_field";

export class GoalProgressBarField extends ProgressBarField {
    static template = "hr_appraisal_skills.GoalProgressBarField";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
    }

    async onClick(){
        const action = this.orm.call('hr.appraisal.skill', 'action_open_current_goals', [[this.props.record.resId]]);
        await this.actionService.doAction(action);
    }
}

export const goalProgressBarField = {
    ...progressBarField,
    component: GoalProgressBarField,
};

registry.category("fields").add("goal_progressbar", goalProgressBarField);
