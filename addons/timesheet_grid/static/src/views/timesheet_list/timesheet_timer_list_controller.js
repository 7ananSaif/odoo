import { useState, useSubEnv } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";

export class TimesheetTimerListController extends ListController {
    static template = "timesheet_grid.TimesheetTimerListController";

    setup() {
        super.setup();
        useSubEnv({
            config: {
                ...this.env.config,
                disableSearchBarAutofocus: true,
            },
        });
        this.timerState = useState({ reload: false });
        this.timerService = useService("timesheet_timer");
    }

    get deleteConfirmationDialogProps() {
        this.timerState.reload = false;
        const dialogProps = super.deleteConfirmationDialogProps;
        if (this.model.root.selection.some((t) => t.data.is_timer_running)) {
            dialogProps.confirm = async () => {
                await this.model.root.deleteRecords();
                this.timerState.reload = true;
            };
        }
        return dialogProps;
    }

    async _processTimerTimesheetUrgentSave() {
        const timesheet = this.timerService.timerState.timesheet;
        if (!timesheet) {
            return;
        }
        let updateTimerState = true;
        if (this.model.root.isGrouped) {
            updateTimerState = await timesheet?.urgentSave();
        }
        if (updateTimerState) {
            this.timerService.updateTimerState(timesheet);
        }
    }

    async beforeUnload() {
        return Promise.all([
            super.beforeUnload(...arguments),
            this._processTimerTimesheetUrgentSave(),
        ]);
    }

    async beforeLeave() {
        return Promise.all([
            super.beforeLeave(...arguments),
            this._processTimerTimesheetUrgentSave(),
        ]);
    }
}
