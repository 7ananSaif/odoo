import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { PosKanbanRenderer } from "./kanban_renderer";
import { PosKanbanController } from "./kanban_controller";

export const posKanbanView = {
    ...kanbanView,
    Renderer: PosKanbanRenderer,
    Controller: PosKanbanController,
};

registry.category("views").add("pos_kanban", posKanbanView);
