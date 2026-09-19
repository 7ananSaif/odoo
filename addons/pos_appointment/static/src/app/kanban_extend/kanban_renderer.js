import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { PosKanbanRecord } from "./kanban_record";
import { PosKanbanHeader } from "./kanban_header";

export class PosKanbanRenderer extends KanbanRenderer {
    static template = "pos_restaurant_appointment.KanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: PosKanbanRecord,
        KanbanHeader: PosKanbanHeader,
    };

    get sortedRecords() {
        return this.group.list.records.sort(
            (a, b) => new Date(a.data.start) - new Date(b.data.start)
        );
    }
}
