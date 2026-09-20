import { patch } from "@web/core/utils/patch";
import { ProjectTaskCalendarCommonRenderer } from "@project/views/project_task_calendar/project_task_calendar_common/project_task_calendar_common_renderer";

patch(ProjectTaskCalendarCommonRenderer.prototype, {
    /**
     * @override
     */
    eventClassNames(info) {
        const classesToAdd = super.eventClassNames(info);
        const { event } = info;
        const highlightIds = this.props.model.highlightIds;
        const record = this.props.model.records[event.id];

        if (record && highlightIds?.length && !highlightIds.includes(record.id)) {
            classesToAdd.push("opacity-25");
        }
        return classesToAdd;
    },
});
