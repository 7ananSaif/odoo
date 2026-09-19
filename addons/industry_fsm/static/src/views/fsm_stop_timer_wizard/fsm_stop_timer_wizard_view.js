import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FsmStopTimerWizardFormController extends FormController {
    setup() {
        super.setup();
        this.timerGeolocation = useService("timer_geolocation");
    }

    /**
     * @override
     */
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_save_timesheet" && this.model.root.data.allow_geolocation) {
            const geolocation = await this.timerGeolocation.getGeoLocation();
            clickParams.context = {
                ...clickParams.context,
                geolocation,
            };
        }
        return super.beforeExecuteActionButton(clickParams);
    }
}

registry.category("views").add("fsm_stop_timer_wizard_form", {
    ...formView,
    Controller: FsmStopTimerWizardFormController,
});
