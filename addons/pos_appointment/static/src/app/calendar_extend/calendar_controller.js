/* global posmodel */

import { AttendeeCalendarController } from "@calendar/views/attendee_calendar/attendee_calendar_controller";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

export class POSAttendeeCalendarController extends AttendeeCalendarController {
    static components = {
        ...AttendeeCalendarController.components,
        QuickCreateFormView: FormViewDialog,
    };

    async onClickAddButton() {
        if (this.props.context.from_pos_booking) {
            const action = await this.orm.call(
                "calendar.event",
                "action_create_booking_form_view",
                [false, posmodel.config.raw.appointment_type_id]
            );
            return this.action.doAction(action, {
                onClose: async () => {
                    this.model.load();
                },
            });
        }
        return super.onClickAddButton(...arguments);
    }
}
