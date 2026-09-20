import { registry } from "@web/core/registry";
import { POSAttendeeCalendarController } from "@pos_appointment/app/calendar_extend/calendar_controller";
import { attendeeCalendarView } from "@calendar/views/attendee_calendar/attendee_calendar_view";

export const posAttendeeCalendarView = {
    ...attendeeCalendarView,
    Controller: POSAttendeeCalendarController,
};

registry.category("views").add("pos_appointment_attendee_calendar", posAttendeeCalendarView);
