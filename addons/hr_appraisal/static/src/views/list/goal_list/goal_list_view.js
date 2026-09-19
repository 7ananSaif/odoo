import { registry } from "@web/core/registry";
import { addFieldDependencies } from "@web/model/relational_model/utils";
import {
    AppraisalGoalDeleteListController,
    appraisalGoalDeleteListView
} from "@hr_appraisal/views/list/goal_template_delete_list/goal_template_delete_list";

import { useGoalStaticAction } from "@hr_appraisal/views/helper/goal_helper_static_actions/goal_helper_static_actions";

export class GoalListController extends AppraisalGoalDeleteListController {
    setup() {
        super.setup();
        // To check if a goal already have a template
        addFieldDependencies(
            this.model.config.activeFields,
            this.model.config.fields,
            [
                { name: 'template_goal_id', type: "many2one" },
                { name: 'child_ids', type: "one2many" },
            ]
        );
    }

    getStaticActionMenuItems() {
        return Object.assign(super.getStaticActionMenuItems(...arguments), useGoalStaticAction(this.model));
    }

    async onClickLibrary() {
        return this.actionService.doAction('hr_appraisal.action_hr_appraisal_goal_template_library', {
            additionalContext: { default_employee_id: this.props.context.default_employee_id }
        });
    }
};


export const goalListView = {
    ...appraisalGoalDeleteListView,
    buttonTemplate: 'hr_appraisal.GoalList.buttons',
    Controller: GoalListController,
};

registry.category("views").add("goal_list_view", goalListView);
