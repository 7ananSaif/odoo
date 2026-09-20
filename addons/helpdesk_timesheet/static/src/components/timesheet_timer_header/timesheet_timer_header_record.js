import { patch } from "@web/core/utils/patch";
import { TimesheetTimerHeaderRecord } from "@timesheet_grid/components/timesheet_timer_header/timesheet_timer_header_record";

patch(TimesheetTimerHeaderRecord.prototype, {
    get fieldNamePerSequence() {
        return {
            ...super.fieldNamePerSequence,
            30: "helpdesk_ticket_id",
        };
    },

    getFieldInfo(fieldName) {
        const fieldInfo = super.getFieldInfo(fieldName);
        let invisible = "";
        if (fieldName === "task_id") {
            if (this.props.timesheet) {
                invisible = "has_helpdesk_team and not task_id";
                fieldInfo.isVisible = !this.evaluateBooleanExpr(
                    invisible,
                    this.props.timesheet.evalContextWithVirtualIds
                );
            }
        } else if (fieldName === "helpdesk_ticket_id") {
            if (this.props.timesheet) {
                invisible = "not has_helpdesk_team and not helpdesk_ticket_id";
                fieldInfo.isVisible = !this.evaluateBooleanExpr(
                    invisible,
                    this.props.timesheet.evalContextWithVirtualIds
                );
                // TODO: check if it is still needed
                fieldInfo.context = `{'default_project_id': project_id}`;
            }
        }
        return fieldInfo;
    },
});
