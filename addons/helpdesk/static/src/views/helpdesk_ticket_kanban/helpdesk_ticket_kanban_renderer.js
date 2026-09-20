import { RottingKanbanRenderer } from '@mail/js/rotting_mixin/rotting_kanban_renderer';
import { HelpdeskTicketKanbanHeader } from './helpdesk_ticket_kanban_header';
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

export class HelpdeskTicketRenderer extends RottingKanbanRenderer {
    static components = {
        ...RottingKanbanRenderer.components,
        KanbanHeader: HelpdeskTicketKanbanHeader,
    };

    setup() {
        super.setup();
        onWillStart(async () => {
            this.isHelpdeskManager = await user.hasGroup('helpdesk.group_helpdesk_manager');
        });
    }

    canCreateGroup() {
        return super.canCreateGroup() && !!this.props.list.context.default_team_id;
    }

    get canResequenceGroups() {
        return super.canResequenceGroups && this.isHelpdeskManager;
    }
}
