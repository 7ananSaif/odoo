import { PlanningGanttModel } from "@planning/views/planning_gantt/planning_gantt_model";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

patch(PlanningGanttModel.prototype, {
    /**
     * @override
     */
    _processGanttData(metaData, data, ganttData) {
        if ("working_periods" in ganttData) {
            const workingPeriods = {};
            for (const [resource_id, periods] of Object.entries(ganttData.working_periods)) {
                workingPeriods[resource_id] = periods.map(({ start, end }) => ({
                        start: deserializeDateTime(start),
                        end: end && deserializeDateTime(end),
                }));
            }
            data.workingPeriods = workingPeriods;
        }
    }
});
