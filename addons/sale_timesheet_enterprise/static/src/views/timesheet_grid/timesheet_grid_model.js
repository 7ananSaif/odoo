import { patch } from "@web/core/utils/patch";
import { TimesheetGridModel } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_model";

patch(TimesheetGridModel.prototype, {
    getTimesheetWorkingHoursPromises(metaData) {
        const promises = super.getTimesheetWorkingHoursPromises(metaData);
        promises.push(this._fetchWorkingHoursData(metaData, "so_line"));
        return promises;
    },
});
