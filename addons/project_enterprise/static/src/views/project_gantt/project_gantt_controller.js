import { GanttController } from "@web_gantt/gantt_controller";

import { ProjectTemplateDropdown } from "@project/views/components/project_template_dropdown";

export class ProjectGanttController extends GanttController {
    static template = "project_enterprise.ProjectGanttController";
    static components = {
        ...GanttController.components,
        ProjectTemplateDropdown,
    };
}
