import { deserializeDate } from "@web/core/l10n/dates";
import { sortBy } from "@web/core/utils/arrays";

import { GanttModel } from "@web_gantt/gantt_model";

import { ProjectTaskModelMixin } from "@project/views/project_task_model_mixin";


export class TaskGanttModelCommon extends ProjectTaskModelMixin(GanttModel) {
    //-------------------------------------------------------------------------
    // Public
    //-------------------------------------------------------------------------

    setup() {
        super.setup(...arguments);
        this.getHighlightIds = () => [];
    }

    async unscheduleTask(id) {
        await this.orm.call("project.task", "action_unschedule_task", [id]);
        this.fetchData();
    }

    //-------------------------------------------------------------------------
    // Protected
    //-------------------------------------------------------------------------

    /**
     * Retrieve the milestone data based on the task domain and the project deadline if applicable.
     * @override
     */
    async _fetchData(metaData, additionalContext) {
        const globalStart = metaData.globalStart.toISODate();
        const globalStop = metaData.globalStop.toISODate();
        const scale = metaData.scale.unit;
        additionalContext = {
            ...(additionalContext || {}),
            gantt_start_date: globalStart,
            gantt_scale: scale,
        };
        const proms = [this.getHighlightIds(), super._fetchData(metaData, additionalContext)];
        let milestones = [];
        const projectDeadlines = [];
        const projectStartDates = [];
        if (!this.orm.isSample && !this.env.isSmall) {
            const prom = this.orm
                .call("project.task", "get_all_deadlines", [globalStart, globalStop], {
                    context: this.searchParams.context,
                })
                .then(({ milestone_id, project_id }) => {
                    milestones = milestone_id.map((m) => ({
                        ...m,
                        deadline: deserializeDate(m.deadline),
                    }));
                    for (const project of project_id) {
                        const dateEnd = project.date;
                        const dateStart = project.date_start;
                        if (dateEnd >= globalStart && dateEnd <= globalStop) {
                            projectDeadlines.push({
                                ...project,
                                date: deserializeDate(dateEnd),
                            });
                        }
                        if (dateStart >= globalStart && dateStart <= globalStop) {
                            projectStartDates.push({
                                ...project,
                                date: deserializeDate(dateStart),
                            });
                        }
                    }
                });
            proms.push(prom);
        }
        this.highlightIds = (await Promise.all(proms))[0];
        this.data.milestones = sortBy(milestones, (m) => m.deadline);
        this.data.projectDeadlines = sortBy(projectDeadlines, (d) => d.date);
        this.data.projectStartDates = sortBy(projectStartDates, (d) => d.date);
    }

    /**
     * @override
     */
    _generateRows(metaData, params) {
        const { groupedBy, groups, parentGroup } = params;
        if (groupedBy.length) {
            const groupedByField = groupedBy[0];
            if (groupedByField === "user_ids") {
                // Here we are generating some rows under a common "parent" (if any).
                // We make sure that a row with resId = false for "user_id"
                // ('Unassigned Tasks') and same "parent" will be added by adding
                // a suitable fake group to groups (a subset of the groups returned
                // by formatted_read_group).
                const fakeGroup = Object.assign({}, ...parentGroup);
                groups.push(fakeGroup);
            }
        }
        const rows = super._generateRows(...arguments);

        // keep empty row to the head and sort the other rows alphabetically
        // except when grouping by stage or personal stage
        if (!["stage_id", "personal_stage_type_ids"].includes(groupedBy[0])) {
            rows.sort((a, b) => {
                if (a.resId && !b.resId) {
                    return 1;
                } else if (!a.resId && b.resId) {
                    return -1;
                } else {
                    return a.name.localeCompare(b.name);
                }
            });
        }
        return rows;
    }

    /**
     * @override
     */
    _getFields(metaData) {
        const result = super._getFields(...arguments);
        // Field data required for muted gantt dependencies
        result.push("is_closed");
        return result;
    }
}
