import { AppointmentBookingGanttController } from "@appointment/views/gantt/gantt_controller";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

export class POSAppointmentBookingGanttController extends AppointmentBookingGanttController {
    /**
     * @override
     * Undo changes from appointment since we open a different form view here
     */
    openDialog(props, options = {}) {
        return super.openDialog(props, options, FormViewDialog);
    }
}
