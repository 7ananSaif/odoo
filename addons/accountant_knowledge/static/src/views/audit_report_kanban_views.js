import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";

export class AuditReportKanbanController extends KanbanController {
    /** @override */
    async createRecord() {
        return this.actionService.doAction(
            "accountant_knowledge.action_audit_report_quick_create",
            {
                onClose: () => this.env.model.load(),
            }
        );
    }

    /** @override */
    async openRecord(record) {
        this.actionService.doAction("knowledge.ir_actions_server_knowledge_home_page", {
            additionalContext: {
                res_id: record.data.knowledge_article_id.id,
            },
        });
    }
}

export const auditReportKanbanController = {
    ...kanbanView,
    Controller: AuditReportKanbanController,
};

registry.category("views").add("audit_report_kanban_controller", auditReportKanbanController);
