import { useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { KanbanController } from "@web/views/kanban/kanban_controller";

export class TimesheetTimerKanbanController extends KanbanController {
    setup() {
        super.setup();
        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: true,
            },
        });
        this.timerService = useService("timesheet_timer");
    }

    async _processTimerTimesheetUrgentSave() {
        const timesheet = this.timerService.timerState.timesheet;
        if (await timesheet?.urgentSave()) {
            this.timerService.updateTimerState(timesheet);
        }
    }

    async beforeUnload() {
        return await Promise.all([
            super.beforeUnload(...arguments),
            this._processTimerTimesheetUrgentSave(),
        ]);
    }

    async beforeLeave() {
        return await Promise.all([
            super.beforeLeave(...arguments),
            this._processTimerTimesheetUrgentSave(),
        ]);
    }
}
