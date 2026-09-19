import { GanttController } from "@web_gantt/gantt_controller";

export class TaskSharingGanttController extends GanttController {
    /** @override */
   _getDialogProps(props) {
        return {
            ...super._getDialogProps(props),
            expandedFormRef: 'project_enterprise.project_sharing_project_task_view_form_inherited_in_gantt',
        };
    }
}
