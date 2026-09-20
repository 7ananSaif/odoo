import { projectTaskActivityView } from "@project/views/project_task_activity/project_task_activity_view";
import { registry } from "@web/core/registry";

import { FsmMyTaskActivityController } from "./fsm_my_task_activity_controller";

export const fsmMyTaskActivityView = {
    ...projectTaskActivityView,
    Controller: FsmMyTaskActivityController,
};

registry.category("views").add("fsm_my_task_activity", fsmMyTaskActivityView);
