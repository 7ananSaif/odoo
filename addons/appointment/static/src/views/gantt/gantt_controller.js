import { GanttController } from "@web_gantt/gantt_controller";
import { AppointmentBookingActionHelper } from "@appointment/components/appointment_booking_action_helper/appointment_booking_action_helper";
import {
    CalendarQuickCreate,
    QUICK_CREATE_CALENDAR_EVENT_FIELDS,
} from "@calendar/views/calendar_form/calendar_quick_create";

// add fields to be carried over when clicking "options" button on quick-edit form dialog
Object.assign(QUICK_CREATE_CALENDAR_EVENT_FIELDS, {
    appointment_status: { type: "string" },
    resource_ids: { type: "many2many" },
    total_capacity_reserved: { type: "number" },
});

const { DateTime } = luxon;

export class AppointmentBookingGanttController extends GanttController {

    static template = "appointment.AppointmentBookingGanttController"
    static components = {
        ...GanttController.components,
        AppointmentBookingActionHelper,
    };
    /**
     * @override
     */
    create(context) {
        super.create({...context, 'booking_gantt_create_record': true})
    }

    /**
     * @override
     * In the Gantt view, if accessed via the appointment.type custom helper should appear when no booking is found.
     * If Gantt view accessed through the schedule views, the helper should appear when no Gantt rows are available.
    */
    get showNoContentHelp() {
        if (!this.props.context.hide_no_content_helper && this.props.context.active_model === "appointment.type") {
            return !this.model.data.records.length;
        } else {
            return !this.model.data.rows || (this.model.data.rows.length == 1 && !this.model.data.rows[0].name)
        }
    }

    /**
     * @override
     * When creating a new booking using the "New" button, round the start datetime to the next
     * half-hour (e.g. 10:12 => 10:30, 11:34 => 12:00).
     * The stop datetime is set by default to start + 1 hour to override the calendar.event's default_stop, which is currently setting the stop based on now instead of start.
     * The stop datetime will be updated in the default_get method on python side to match the appointment type duration.
    */
    _onAddClicked() {
        const focusDate = this.getCurrentFocusDate();
        const now = DateTime.now();
        const start =
            now.minute > 30
                ? focusDate.set({ hour: now.hour + 1, minute: 0, second: 0 })
                : focusDate.set({ hour: now.hour, minute: 30, second: 0 });
        const stop = start.plus({ hour: 1 });
        const context = this.model.getDialogContext({ start, stop, withDefault: true });
        this.create(context);
    }

    /**
     * @override
     * Add props required by the quick create form view
     * and open the calendar-specific form dialog
     * unless otherwise specified.
     */
    openDialog(props, options = {}, dialogComponent = null) {
        if (dialogComponent !== null) {
            return super.openDialog(...arguments);
        }
        return super.openDialog(props, options, CalendarQuickCreate);
    }
}
