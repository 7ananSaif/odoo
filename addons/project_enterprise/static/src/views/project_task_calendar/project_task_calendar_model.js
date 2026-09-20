import { Domain } from "@web/core/domain";
import { deserializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { ProjectTaskCalendarModel } from "@project/views/project_task_calendar/project_task_calendar_model";
import { useProjectModelActions } from "../project_highlight_tasks";

patch(ProjectTaskCalendarModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.getHighlightIds = useProjectModelActions({
            getContext: () => this.env.searchModel._context,
        }).getHighlightIds;
    },

    get tasksToPlanDomain() {
        return Domain.and([
            super.tasksToPlanDomain,
            [['planned_date_begin', '=', false]],
        ]);
    },

    /**
     * @override
     */
    async loadRecords(data) {
        this.highlightIds = await this.getHighlightIds();
        return await super.loadRecords(data);
    },

    _getPlanTaskVals(taskToPlan, date, timeSlotSelected = false) {
        const planTaskVals = super._getPlanTaskVals(taskToPlan, date, timeSlotSelected);
        if (timeSlotSelected) {
            const end = date.plus({ hours: 1 });
            planTaskVals["planned_date_begin"] = serializeDateTime(date);
            planTaskVals["date_deadline"] = serializeDateTime(end);
        } else if (["day", "week"].includes(this.meta.scale)) {
            const [start, end] = this.getAllDayDates(date, date);
            planTaskVals["planned_date_begin"] = serializeDateTime(start);
            planTaskVals["date_deadline"] = serializeDateTime(end);
        }
        return planTaskVals;
    },
});

export class ProjectEnterpriseTaskCalendarModel extends ProjectTaskCalendarModel {
    makeContextDefaults(record) {
        const { default_planned_date_start, ...context } = super.makeContextDefaults(record);
        if (
            ["day", "week"].includes(this.meta.scale) ||
            !deserializeDate(default_planned_date_start).hasSame(
                deserializeDate(context["default_date_deadline"]),
                "day"
            )
        ) {
            context.default_planned_date_begin = default_planned_date_start;
        }

        return { ...context, scale: this.meta.scale };
    }
}
