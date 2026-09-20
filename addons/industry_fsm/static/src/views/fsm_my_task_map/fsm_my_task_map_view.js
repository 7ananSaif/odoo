import { registry } from "@web/core/registry";
import { FsmMyTaskMapController } from "./fsm_my_task_map_controller";
import { fsmTaskMapView } from "../fsm_task_map/fsm_task_map_view";

export const fsmMyTaskMapView = {
    ...fsmTaskMapView,
    Controller: FsmMyTaskMapController,
};

registry.category("views").add("fsm_my_task_map", fsmMyTaskMapView);
