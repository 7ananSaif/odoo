import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { AppointmentTemplatePickerDialog } from "@appointment/components/appointment_template_picker_dialog/appointment_template_picker_dialog";

export class AppointmentTypeListController extends ListController {
    setup() {
        super.setup();
        this.dialog = useService("dialog");
    }
    /**
     * @override
     */
    async createRecord() {
        this.dialog.add(AppointmentTemplatePickerDialog, {});
    }
}
