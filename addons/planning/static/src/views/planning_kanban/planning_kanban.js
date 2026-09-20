import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { PlanningSearchModel } from "../planning_search_model";
import { PlanningRelationalModel } from "../planning_relational_model";
import { PlanningKanbanController } from "./planning_kanban_controller";


registry.category("views").add("planning_kanban", {
    ...kanbanView,
    Controller: PlanningKanbanController,
    SearchModel: PlanningSearchModel,
    Model: PlanningRelationalModel,
});
