import { useService } from "@web/core/utils/hooks";
import { FormController } from '@web/views/form/form_controller';
import { AppointmentTemplatePickerDialog } from "@appointment/components/appointment_template_picker_dialog/appointment_template_picker_dialog";

export class AppointmentTypeFormController extends FormController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    /**
     * @override
     */
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "add_videocall_source") {
            this.model.root.update({'event_videocall_source': 'discuss'});
            return false;
        }
        return super.beforeExecuteActionButton(...arguments);
    }

    /**
     * @override
     */
    async create() {
        this.dialog.add(AppointmentTemplatePickerDialog, {});
    }
}
