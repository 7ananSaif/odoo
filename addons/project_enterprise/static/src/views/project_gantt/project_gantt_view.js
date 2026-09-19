import { ganttView } from "@web_gantt/gantt_view";
import { registry } from "@web/core/registry";
import { ProjectGanttController } from "./project_gantt_controller";
import { ProjectGanttRenderer } from "./project_gantt_renderer";
import { ProjectGanttModel } from "./project_gantt_model";

export const projectGanttView = {
    ...ganttView,
    Controller: ProjectGanttController,
    Renderer: ProjectGanttRenderer,
    Model: ProjectGanttModel,
};

registry.category("views").add("project_gantt", projectGanttView);
