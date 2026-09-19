import { useEffect } from "@odoo/owl";

import { localization } from "@web/core/l10n/localization";
import { usePopover } from "@web/core/popover/popover_hook";

import { GanttRenderer } from "@web_gantt/gantt_renderer";

import { MilestonesPopover } from "./milestones_popover";


export class TaskGanttRendererCommon extends GanttRenderer {
    static headerTemplate = "project_enterprise.TaskGanttRenderer.Header";
    static rowContentTemplate = "project_enterprise.TaskGanttRenderer.RowContent";
    static totalRowTemplate = "project_enterprise.TaskGanttRenderer.TotalRow";
    static pillTemplate = "project_enterprise.TaskGanttRenderer.Pill";

    setup() {
        super.setup(...arguments);
        useEffect(
            (el) => el.classList.add("o_project_gantt"),
            () => [this.gridRef.el]
        );
        const position = localization.direction === "rtl" ? "bottom" : "right";
        this.milestonePopover = usePopover(MilestonesPopover, { position });
    }

    /**
     * @override
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        if (enrichedPill.record.is_closed) {
            pill.className += " opacity-50";
        }
        return enrichedPill;
    }

    computeVisibleColumns() {
        super.computeVisibleColumns();
        this.columnMilestones = {}; // deadlines and milestones by project
        for (const column of this.columns) {
            this.columnMilestones[column.index] = {
                hasDeadLineExceeded: false,
                allReached: true,
                projects: {},
                hasMilestone: false,
                hasDeadline: false,
                hasStartDate: false,
            };
        }
        // Handle start date at the beginning of the current period
        this.columnMilestones[this.columns[0].index].edge = {
            projects: {},
            hasStartDate: false,
        };
        const projectStartDates = [...this.model.data.projectStartDates];
        const projectDeadlines = [...this.model.data.projectDeadlines];
        const milestones = [...this.model.data.milestones];

        let project = projectStartDates.shift();
        let projectDeadline = projectDeadlines.shift();
        let milestone = milestones.shift();
        let i = 0;
        while (i < this.columns.length && (project || projectDeadline || milestone)) {
            const column = this.columns[i];
            const nextColumn = this.columns[i + 1];
            const info = this.columnMilestones[column.index];

            if (i == 0 && project && column && column.stop > project.date) {
                // For the first column, start dates have to be displayed at the start of the period
                if (!info.edge.projects[project.id]) {
                    info.edge.projects[project.id] = {
                        milestones: [],
                        id: project.id,
                        name: project.name,
                    };
                }
                info.edge.projects[project.id].isStartDate = true;
                info.edge.hasStartDate = true;
                project = projectStartDates.shift();
            } else if (project && nextColumn?.stop > project.date) {
                if (!info.projects[project.id]) {
                    info.projects[project.id] = {
                        milestones: [],
                        id: project.id,
                        name: project.name,
                    };
                }
                info.projects[project.id].isStartDate = true;
                info.hasStartDate = true;
                project = projectStartDates.shift();
            }

            if (projectDeadline && column.stop > projectDeadline.date) {
                if (!info.projects[projectDeadline.id]) {
                    info.projects[projectDeadline.id] = {
                        milestones: [],
                        id: projectDeadline.id,
                        name: projectDeadline.name,
                    };
                }
                info.projects[projectDeadline.id].isDeadline = true;
                info.hasDeadline = true;
                projectDeadline = projectDeadlines.shift();
            }

            if (milestone && column.stop > milestone.deadline) {
                const [projectId, projectName] = milestone.project_id;
                if (!info.projects[projectId]) {
                    info.projects[projectId] = {
                        milestones: [],
                        id: projectId,
                        name: projectName,
                    };
                }
                const { is_deadline_exceeded, is_reached } = milestone;
                info.projects[projectId].milestones.push(milestone);
                info.hasMilestone = true;
                milestone = milestones.shift();
                if (is_deadline_exceeded) {
                    info.hasDeadLineExceeded = true;
                }
                if (!is_reached) {
                    info.allReached = false;
                }
            }
            if (
                (!project || !nextColumn || nextColumn?.stop < project.date) &&
                (!projectDeadline || column.stop < projectDeadline.date) &&
                (!milestone || column.stop < milestone.deadline)
            ) {
                i++;
            }
        }
    }

    async getPopoverProps(pill) {
        const props = await super.getPopoverProps(...arguments);
        props.actionContext.is_form_gantt = true;
        return props;
    }

    shouldRenderRecordConnectors(record) {
        if (record.allow_task_dependencies) {
            return super.shouldRenderRecordConnectors(...arguments);
        }
        return false;
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    onMilestoneMouseEnter(ev, projects) {
        this.milestonePopover.open(ev.target, {
            displayMilestoneDates: this.model.metaData.scale.id === "year",
            displayProjectName: !this.model.searchParams.context.default_project_id,
            projects,
        });
    }

    onMilestoneMouseLeave() {
        this.milestonePopover.close();
    }

    //--------------------------------------------------------------------------
    //Task Connectors
    //--------------------------------------------------------------------------

    shouldConnectorBeDashed(sourcePill) {
        if (sourcePill.record.is_closed) {
            return true;
        }
        return super.shouldConnectorBeDashed(sourcePill);
    }

}
