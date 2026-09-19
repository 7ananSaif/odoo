import { registry } from "@web/core/registry";
import { TimesheetTimerListController } from "./timesheet_timer_list_controller";
import { TimesheetTimerListRenderer } from "./timesheet_timer_list_renderer";
import { listView } from "@web/views/list/list_view";

class TimesheetTimerListModel extends listView.Model {
    static withCache = false;
}

export const timesheetTimerListView = {
    ...listView,
    Controller: TimesheetTimerListController,
    Model: TimesheetTimerListModel,
    Renderer: TimesheetTimerListRenderer,
};

registry.category("views").add("timesheet_timer_list", timesheetTimerListView);
