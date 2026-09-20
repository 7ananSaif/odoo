import { KanbanHeader } from "@web/views/kanban/kanban_header";

export class PosKanbanHeader extends KanbanHeader {
    static template = "pos_restaurant_appointment.KanbanHeader";

    get totalCapacityReserved() {
        return this.props.group.list.records.reduce(
            (sum, record) => sum + record.data.waiting_list_capacity,
            0
        );
    }
}
