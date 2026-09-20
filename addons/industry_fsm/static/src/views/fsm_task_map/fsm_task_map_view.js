import { registry } from "@web/core/registry";
import { projectTaskMapView } from "@project_enterprise/views/project_task_map/project_task_map_view";
import { FsmTaskMapRenderer } from "./fsm_task_map_renderer";

export const fsmTaskMapView = {
    ...projectTaskMapView,
    Renderer: FsmTaskMapRenderer,
};

registry.category("views").add("fsm_task_map", fsmTaskMapView);
