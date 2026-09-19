import { timesheetCalendarMyTimesheetsView } from "@hr_timesheet/views/timesheet_calendar_my_timesheets/timesheet_calendar_my_timesheets_view";
import { patch } from "@web/core/utils/patch";
import { TimesheetCalendarMyTimesheetsController } from "./timesheet_calendar_my_timesheets_controller";

patch(timesheetCalendarMyTimesheetsView, {
    Controller: TimesheetCalendarMyTimesheetsController
});
