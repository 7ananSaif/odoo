import { user } from "@web/core/user";
import { GanttModel } from "@web_gantt/gantt_model";
import { ProjectModelMixin } from "@project/views/project_model_mixin";

const COLOR_FIELD = "stage_id";

export class ProjectGanttModel extends ProjectModelMixin(GanttModel) {
    /**
     * @override
     */
    async load(searchParams) {
        const stagesEnabled = await user.hasGroup("project.group_project_stages");
        if (stagesEnabled && !this.metaData.colorField) {
            // This is equivalent to setting a color attribute for the gantt view, but only when we have read access to
            // the field (i.e. the user has the 'project.group_project_stages' group).
            this.metaData.colorField = COLOR_FIELD;
        }
        searchParams.domain = this._processSearchDomain(searchParams?.domain || []);
        await super.load(searchParams);
    }

    /**
     * @override
     */
    _reschedule(ids, data, context) {
        return this.orm.call(this.metaData.resModel, "web_gantt_write", [ids, data], {
            context,
        });
    }

    /**
     * @override
     */
    _generateRows(metaData, params) {
        const { groupedBy, groups, parentGroup } = params;
        if (groupedBy.length) {
            const groupedByField = groupedBy[0];
            if (groupedByField === "user_id") {
                // Here we are generating some rows under a common "parent" (if any).
                // We make sure that a row with resId = false for "user_id"
                // ('Unassigned Projects') and same "parent" will be added by adding
                // a suitable fake group to groups (a subset of the groups returned
                // by read_group).
                const fakeGroup = Object.assign({}, ...parentGroup);
                groups.push(fakeGroup);
            }
        }
        const rows = super._generateRows(...arguments);

        // keep empty row to the head and sort the other rows alphabetically
        // except when grouping by stage
        if ("stage_id" != groupedBy[0]) {
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
}
