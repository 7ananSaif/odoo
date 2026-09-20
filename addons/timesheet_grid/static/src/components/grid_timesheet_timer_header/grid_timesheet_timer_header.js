import { useService } from "@web/core/utils/hooks";
import { Record } from "@web/model/record";

import { Component, onWillStart, useState } from "@odoo/owl";

import { TimesheetTimerHeader } from "../timesheet_timer_header/timesheet_timer_header";

export class GridTimesheetTimerHeader extends Component {
    static components = {
        TimesheetTimerHeader,
        Record,
    };
    static props = {
        model: Object,
        updateTimesheet: Function,
        onTimerStarted: Function,
        onTimerStopped: Function,
        onTimerUnlinked: Function,
    };
    static template = "timesheet_grid.GridTimesheetTimerHeader";

    setup() {
        this.notificationService = useService("notification");
        this.timesheetUOMService = useService("timesheet_uom");
        this.timerService = useService("timesheet_timer");
        this.timerState = useState(this.timerService.timerState);
        this.recordHooks = {
            onRecordChanged: this.onTimesheetChanged.bind(this),
        };
        onWillStart(this.onWillStart);
    }

    async onWillStart() {
        if (!this.timerService.timesheetTimerFields) {
            await this.timerService.fetchTimerHeaderFields(this.fieldNames);
        }
    }

    get fieldNames() {
        return ["name", "project_id", "task_id", "company_id", "timer_start", "unit_amount"];
    }

    get isMobile() {
        return this.env.isSmall;
    }

    get timerRunning() {
        return this.timerState.isRunning;
    }

    get activeFields() {
        const activeFields = {};
        for (const fieldName of this.fieldNames) {
            activeFields[fieldName] = this.timerService.getTimesheetTimerFieldInfo(fieldName);
        }
        return activeFields;
    }

    async onTimesheetChanged(timesheet, changes) {
        const secondsElapsed = this.timerService.timer.toSeconds;
        if (timesheet.isNew) {
            if (changes.project_id || changes.task_id) {
                // create the timesheet when the project is set
                timesheet.save({ reload: false }).then(() => {
                    this.timerService.updateTimerState(timesheet);
                    this.props.updateTimesheet(this.timerService.timerState.data, secondsElapsed);
                });
            }
            // Nothing to do since because a timesheet cannot be created without a project set or it is not a manual change.
            return;
        }
        if (
            changes.name === "" &&
            Object.keys(changes).length === 1 &&
            ((!("name" in this.props.model.data.timer) &&
                this.props.model.data.timer.description === "/") ||
                this.props.model.data.timer.name === "/")
        ) {
            return; // nothing to do
        }
        this.timerService.updateTimerState(timesheet);
        this.props.updateTimesheet(this.timerService.timerState.data);
        if (timesheet._checkValidity({ displayNotification: false })) {
            timesheet.save({ reload: false });
        }
    }
}
