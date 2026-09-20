import { serializeDateTime } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";

import { ProjectTaskCalendarModel } from '@project/views/project_task_calendar/project_task_calendar_model';
import { ProjectEnterpriseTaskCalendarModel } from "@project_enterprise/views/project_task_calendar/project_task_calendar_model";

export class FsmTaskCalendarModel extends ProjectTaskCalendarModel {
    setup() {
        super.setup(...arguments);
        this.meta.scale = this.env.isSmall? "day" : this.meta.scale;
    }

    _getPlanTaskVals(taskToPlan, date, timeSlotSelected = false) {
        const planTaskVals = super._getPlanTaskVals(...arguments);
        if (!timeSlotSelected) {
            const [start, end] = this.getAllDayDates(date, date);
            planTaskVals["planned_date_begin"] = serializeDateTime(start);
            planTaskVals["date_deadline"] = serializeDateTime(end);
        }
        return planTaskVals;
    }

    _getPlanTaskContext(taskToPlan, timeSlotSelected) {
        const context = super._getPlanTaskContext(...arguments);
        if (!timeSlotSelected) {
            context.task_calendar_plan_full_day = true;
        }
        return context;
    }

    makeContextDefaults(record) {
        const { default_planned_date_start, ...context } = super.makeContextDefaults(record);
        return {
            ...context,
            default_planned_date_begin: default_planned_date_start,
        };
    }
}

patch(ProjectEnterpriseTaskCalendarModel.prototype, {
    get tasksToPlanSpecification() {
        const tasksToPlanSpecification = super.tasksToPlanSpecification;
        tasksToPlanSpecification['is_fsm'] = {};
        return tasksToPlanSpecification;
    },

    _getPlanTaskVals(taskToPlan, date, timeSlotSelected = false) {
        const planTaskVals = super._getPlanTaskVals(...arguments);
        if (!timeSlotSelected && taskToPlan.is_fsm) {
            const [start, end] = this.getAllDayDates(date, date);
            planTaskVals["planned_date_begin"] = serializeDateTime(start);
            planTaskVals["date_deadline"] = serializeDateTime(end);
        }
        return planTaskVals;
    },

    _getPlanTaskContext(taskToPlan, timeSlotSelected) {
        const context = super._getPlanTaskContext(...arguments);
        if (taskToPlan.is_fsm && !timeSlotSelected) {
            context.task_calendar_plan_full_day = true;
        }
        return context;
    },
});
