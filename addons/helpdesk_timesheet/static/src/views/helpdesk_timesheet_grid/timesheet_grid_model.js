import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { TimesheetGridModel } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_model";

patch(TimesheetGridModel.prototype, {
    /**
     * @override
     */
    _getPreviousWeekTimesheetDomain() {
        return Domain.and([super._getPreviousWeekTimesheetDomain(), [["helpdesk_ticket_id", "=", false]]]);
    },
});
