import { PlanningGanttModel } from "@planning/views/planning_gantt/planning_gantt_model";

export class ForecastGanttModel extends PlanningGanttModel {
    load(searchParams) {
        const groupBy = searchParams.groupBy.slice();
        if (searchParams.context.planning_groupby_project && !groupBy.length) {
            groupBy.unshift("project_id");
        }
        return super.load({ ...searchParams, groupBy });
    }
}
