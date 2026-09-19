import { registry } from "@web/core/registry";
import { rottingKanbanView } from "@mail/js/rotting_mixin/rotting_kanban_view";
import { HelpdeskTicketRenderer } from './helpdesk_ticket_kanban_renderer';

export const helpdeskTicketKanbanView = {
    ...rottingKanbanView,
    Renderer: HelpdeskTicketRenderer,
};

registry.category('views').add('helpdesk_ticket_kanban', helpdeskTicketKanbanView);
