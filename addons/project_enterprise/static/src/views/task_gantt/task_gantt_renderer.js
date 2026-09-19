import { SelectCreateAutoPlanDialog } from "@project_enterprise/views/view_dialogs/select_auto_plan_create_dialog";
import { _t } from "@web/core/l10n/translation";
import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { markup, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

import { TaskGanttRendererCommon } from "@project_enterprise/views/project_task_common/task_gantt_renderer_common";
import { TaskGanttRendererControls } from "./task_gantt_renderer_controls";


export class TaskGanttRenderer extends TaskGanttRendererCommon {
    static components = {
        ...TaskGanttRendererCommon.components,
        GanttRendererControls: TaskGanttRendererControls,
        Avatar,
    };
    static rowHeaderTemplate = "project_enterprise.TaskGanttRenderer.RowHeader";
    setup() {
        super.setup(...arguments);
        this.notificationService = useService("notification");
        this.orm = useService("orm");
        useEffect(
            (el) => el.classList.add("o_project_gantt"),
            () => [this.gridRef.el]
        );
    }

    /**
     * @override
     */
    enrichPill(pill) {
        const enrichedPill = super.enrichPill(pill);
        if (enrichedPill?.record) {
            if (
                this.props.model.highlightIds &&
                    !this.props.model.highlightIds.includes(enrichedPill.record.id)
            ) {
                pill.className += " opacity-25";
            }
        }
        return enrichedPill;
    }

    computeDerivedParams() {
        this.rowsWithAvatar = {};
        super.computeDerivedParams();
    }

    getConnectorAlert(masterRecord, slaveRecord) {
        if (
            masterRecord.display_warning_dependency_in_gantt &&
            slaveRecord.display_warning_dependency_in_gantt
        ) {
            return super.getConnectorAlert(...arguments);
        }
    }

    getAvatarProps(row) {
        return this.rowsWithAvatar[row.id];
    }

    getSelectCreateDialogProps() {
        const props = super.getSelectCreateDialogProps(...arguments);
        const onCreateEdit = () => {
            this.dialogService.add(FormViewDialog, {
                context: props.context,
                resModel: props.resModel,
                onRecordSaved: async (record) => {
                    await record.save({ reload: false });
                    await this.model.fetchData();
                },
            });
        };
        const onSelectedAutoPlan = (resIds) => {
            props.context.smart_task_scheduling = true;
            if (resIds.length) {
                this.model.reschedule(
                    resIds,
                    props.context,
                    this.openPlanDialogCallback.bind(this)
                );
            }
        };
        props.onSelectedNoSmartSchedule = props.onSelected;
        props.onSelected = onSelectedAutoPlan;
        props.onCreateEdit = onCreateEdit;
        return props;
    }

    hasAvatar(row) {
        return row.id in this.rowsWithAvatar;
    }

    getNotificationOnSmartSchedule(notifText, old_vals_per_task_id, type) {
        this.closeNotificationFn?.();
        this.closeNotificationFn = this.notificationService.add(
            markup`<i class="fa btn-link fa-check"></i><span class="ms-1">${notifText}</span>`,
            {
                type: type,
                sticky: true,
                buttons: [
                    {
                        name: "Undo",
                        icon: "fa-undo",
                        onClick: async () => {
                            const ids = Object.keys(old_vals_per_task_id).map(Number);
                            await this.orm.call("project.task", "action_rollback_auto_scheduling", [
                                ids,
                                old_vals_per_task_id,
                            ]);
                            this.model.toggleHighlightPlannedFilter(false);
                            this.closeNotificationFn();
                            await this.model.fetchData();
                        },
                    },
                ],
            }
        );
    }

    openPlanDialogCallback(res) {
        if (res && Array.isArray(res)) {
            const warnings = Object.entries(res[0]);
            const old_vals_per_task_id = res[1];
            const has_tasks_planned = Object.keys(old_vals_per_task_id).length > 0;
            const has_warnings = warnings.length > 0

            if (!has_warnings && !has_tasks_planned) {
                return;
            }

            for (const warning of warnings) {
                this.notificationService.add(warning[1], {
                    type: "warning",
                    sticky: true,
                });
            }

            if (has_tasks_planned) {
                const notif_text = has_warnings ?
                    _t("Some tasks have been successfully scheduled for the upcoming periods. Some warnings were generated. Please review them for details.") :
                    _t("Tasks have been successfully scheduled for the upcoming periods.")
                ;
                const type = has_warnings ? "warning" : "success";
                this.getNotificationOnSmartSchedule(
                    notif_text,
                    old_vals_per_task_id,
                    type,
                );
            }
        }
    }

    processRow(row) {
        const { groupedByField, name, resId } = row;
        if (groupedByField === "user_ids" && Boolean(resId)) {
            const { fields } = this.model.metaData;
            const resModel = fields.user_ids.relation;
            this.rowsWithAvatar[row.id] = { resModel, resId, displayName: name };
        }
        return super.processRow(...arguments);
    }

    highlightPill(pillId, highlighted) {
        if (!this.connectorDragState.dragging) {
            return super.highlightPill(pillId, highlighted);
        }
        const pill = this.pills[pillId];
        if (!pill) {
            return;
        }
        const { record } = pill;
        if (!this.shouldRenderRecordConnectors(record)) {
            return super.highlightPill(pillId, false);
        }
        return super.highlightPill(pillId, highlighted);
    }

    onConnectorHover() {
        return !this.connectorDragState.dragging;
    }

    onPlan(rowId, columnStart, columnStop) {
        let { start, stop } = this.getColumnStartStop(columnStart, columnStop);
        ({ start, stop } = this.normalizeTimeRange(start, stop));
        this.dialogService.add(
            SelectCreateAutoPlanDialog,
            this.getSelectCreateDialogProps({ rowId, start, stop, withDefault: true })
        );
    }

    getUndoAfterDragMessages(dragAction) {
        if (dragAction === "copy") {
            return {
                success: _t("Task duplicated"),
                undo: _t("Task removed"),
                failure: _t("Task could not be removed"),
            };
        }
        return {
            success: _t("Task rescheduled"),
            undo: _t("Task reschedule undone"),
            failure: _t("Failed to undo reschedule"),
        };
    }

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /*
     * @overwrite
     */
    onRemoveButtonClick(connectorId) {
        const { sourcePillId, targetPillId } = this.mappingConnectorToPills[connectorId];
        this.highlightPill(sourcePillId, false);
        this.highlightPill(targetPillId, false);
        super.onRemoveButtonClick(connectorId);
    }
}
