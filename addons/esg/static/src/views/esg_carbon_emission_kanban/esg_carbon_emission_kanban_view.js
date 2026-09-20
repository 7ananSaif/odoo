import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { EsgCarbonEmissionKanbanController } from "./esg_carbon_emission_kanban_controller";

export const EsgCarbonEmissionKanbanView = {
    ...kanbanView,
    Controller: EsgCarbonEmissionKanbanController,
};

registry.category("views").add("esg_carbon_emission_kanban", EsgCarbonEmissionKanbanView);
