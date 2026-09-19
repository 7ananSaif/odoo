import { GanttController } from "@web_gantt/gantt_controller";

import { ProjectTaskTemplateDropdown } from "@project/views/components/project_task_template_dropdown";

export class TaskGanttController extends GanttController {
    static template = "project_enterprise.TaskGanttController";
    static components = {
        ...GanttController.components,
        ProjectTaskTemplateDropdown,
    };
}
