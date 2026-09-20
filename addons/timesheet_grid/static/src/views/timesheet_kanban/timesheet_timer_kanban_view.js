import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { TimesheetTimerKanbanController } from "./timesheet_timer_kanban_controller";
import { TimesheetTimerKanbanRenderer } from "./timesheet_timer_kanban_renderer";

class TimesheetTimerKanbanModel extends kanbanView.Model {
    static withCache = false;
}

export const timesheetTimerKanbanView = {
    ...kanbanView,
    Controller: TimesheetTimerKanbanController,
    Model: TimesheetTimerKanbanModel,
    Renderer: TimesheetTimerKanbanRenderer,
};

registry.category("views").add("timesheet_timer_kanban", timesheetTimerKanbanView);
