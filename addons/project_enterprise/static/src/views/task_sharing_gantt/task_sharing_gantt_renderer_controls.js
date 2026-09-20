import { GanttRendererControls } from "@web_gantt/gantt_renderer_controls";

export class TaskSharingGanttRendererControls extends GanttRendererControls {

    get displayRescheduleMethods() {
        return false;
    }
}
