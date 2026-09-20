import { ListRenderer } from "@web/views/list/list_renderer";
import { TimesheetTimerHeader } from "@timesheet_grid/components/timesheet_timer_header/timesheet_timer_header";
import { useTimesheetTimer } from "@timesheet_grid/hooks/use_timesheet_timer";

export class TimesheetTimerListRenderer extends ListRenderer {
    static template = "timesheet_grid.TimesheetTimerListRenderer";
    static components = {
        ...ListRenderer.components,
        TimesheetTimerHeader: TimesheetTimerHeader,
    };
    static props = [...ListRenderer.props, "timerState"];

    setup() {
        super.setup();
        this.timesheetTimerHook = useTimesheetTimer(true);
        this.timesheetTimerService = this.timesheetTimerHook.timesheetTimerService;
    }

    onGlobalClick(ev) {
        if (ev.target.closest(".timesheet-timer")) {
            return;
        }
        super.onGlobalClick(ev);
    }
}
