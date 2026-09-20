import { KanbanController } from "@web/views/kanban/kanban_controller";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { AppointmentTemplatePickerDialog } from "@appointment/components/appointment_template_picker_dialog/appointment_template_picker_dialog";

export class AppointmentTypeKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.actionService = useService('action');
        this.dialog = useService("dialog");
    }

    /**
     * @override
     */
    async createRecord() {
        this.dialog.add(AppointmentTemplatePickerDialog, {});
    }

    onClickShareAppointmentLink() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'appointment.invite',
            name: _t('Share Appointment'),
            views: [[false, 'form']],
            target: 'new',
            context: {dialog_size: 'medium'},
        });
    }
}
