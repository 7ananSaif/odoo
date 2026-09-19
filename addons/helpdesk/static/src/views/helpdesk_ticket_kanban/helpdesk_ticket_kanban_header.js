import { RottingKanbanHeader } from "@mail/js/rotting_mixin/rotting_kanban_header";
import { HelpdeskTicketGroupConfigMenu } from "../helpdesk_ticket_group_config_menu";

export class HelpdeskTicketKanbanHeader extends RottingKanbanHeader {
    static components = {
        ...RottingKanbanHeader.components,
        GroupConfigMenu: HelpdeskTicketGroupConfigMenu,
    };
}
