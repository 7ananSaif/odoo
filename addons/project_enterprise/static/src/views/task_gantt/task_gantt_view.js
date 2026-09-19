import { ProjectTaskControlPanel } from "@project/views/project_task_control_panel/project_task_control_panel";

import { ganttView } from "@web_gantt/gantt_view";
import { TaskGanttController } from "./task_gantt_controller";
import { registry } from "@web/core/registry";
import { TaskGanttArchParser } from "./task_gantt_arch_parser";
import { TaskGanttModel } from "./task_gantt_model";
import { TaskGanttRenderer } from "./task_gantt_renderer";

const viewRegistry = registry.category("views");

export const taskGanttView = {
    ...ganttView,
    ControlPanel: ProjectTaskControlPanel,
    Controller: TaskGanttController,
    ArchParser: TaskGanttArchParser,
    Model: TaskGanttModel,
    Renderer: TaskGanttRenderer,
};

viewRegistry.add("task_gantt", taskGanttView);
