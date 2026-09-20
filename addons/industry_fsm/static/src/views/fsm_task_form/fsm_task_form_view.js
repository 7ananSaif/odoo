import { ProjectTaskFormController } from "@project/views/project_task_form/project_task_form_controller";
import { projectTaskFormView } from "@project/views/project_task_form/project_task_form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FsmProjectTaskFormController extends ProjectTaskFormController {
    setup() {
        super.setup();
        this.timerGeolocation = useService("timer_geolocation");
    }

    /**
     * @override
     */
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_timer_start" && this.model.root.data.allow_geolocation) {
            const geolocation = await this.timerGeolocation.getGeoLocation();
            clickParams.context = {
                ...clickParams.context,
                geolocation,
            };
        }
        return super.beforeExecuteActionButton(...arguments);
    }
}

registry.category("views").add("fsm_project_task_form", {
    ...projectTaskFormView,
    Controller: FsmProjectTaskFormController,
});
