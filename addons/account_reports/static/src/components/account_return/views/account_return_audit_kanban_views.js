import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { AccountReturnBaseKanbanRenderer } from "./account_return_base_kanban_renderer";

export const accountReturnAuditKanbanView = {
    ...kanbanView,
    Renderer: AccountReturnBaseKanbanRenderer,
};

registry.category("views").add("account_return_audit_kanban", accountReturnAuditKanbanView);
