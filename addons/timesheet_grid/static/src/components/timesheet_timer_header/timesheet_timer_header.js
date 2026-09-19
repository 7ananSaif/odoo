import { Component, useState } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { TimesheetTimerHeaderButtons } from "./timesheet_timer_header_buttons";
import { TimesheetTimerHeaderRecord } from "./timesheet_timer_header_record";

export class TimesheetTimerHeader extends Component {
    static template = "timesheet_grid.TimesheetTimerHeader";
    static components = {
        TimesheetTimerHeaderButtons,
        TimesheetTimerHeaderRecord,
    };
    static props = {
        slots: { type: Object, optional: true },
        timesheet: { type: Object, optional: true },
        fields: { type: Object, optional: true },
        onTimerStarted: Function,
        onTimerStopped: Function,
        onTimerUnlinked: Function,
        onClick: { type: Function, optional: true },
        className: { type: String, optional: true },
    };
    static defaultProps = {
        onClick() {},
    };

    setup() {
        this.timerService = useService("timesheet_timer");
        this.timerState = useState(this.timerService.timerState);
    }

    get classNames() {
        const displayFlex = this.isMobile && !this.timerState.isRunning;
        const classNames = {
            "d-flex": displayFlex,
            "d-grid": !displayFlex,
        };
        if (this.props.className) {
            classNames[this.props.className] = true;
        }
        return classNames;
    }

    get isMobile() {
        return this.env.isSmall;
    }

    async stopTimer(ev) {
        if (await this.props.timesheet.save()) {
            this.props.onTimerStopped();
        }
    }
}
