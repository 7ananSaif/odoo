import { getRawValue } from "@web/views/kanban/kanban_record";
import { ListRenderer } from '@web/views/list/list_renderer';

import { HelpdeskTicketGroupConfigMenu } from '../helpdesk_ticket_group_config_menu';

export class HelpdeskTicketListRenderer extends ListRenderer {
    static components = {
        ...ListRenderer.components,
        GroupConfigMenu: HelpdeskTicketGroupConfigMenu,
    };

    get canCreateGroup() {
        return super.canCreateGroup && !!this.props.list.context.default_team_id;
    }

    getSelectedTicketSameTeam() {
        if (this._selectedTicketSameTeam === undefined) {
            const { selection } = this.props.list;
            if (selection.length) {
                const ticketId = getRawValue(selection[0], "team_id");
                this._selectedTicketSameTeam = selection.every(
                    (ticket) => getRawValue(ticket, "team_id") === ticketId
                );
                Promise.resolve().then(() => {
                    delete this._selectedTicketSameTeam;
                });
            }
        }
        return this._selectedTicketSameTeam;
    }

    isCellReadonly(column, record) {
        let readonly = false;
        if (column.name === "stage_id") {
            readonly = !this.getSelectedTicketSameTeam();
        }
        return readonly || super.isCellReadonly(column, record);
    }
}
