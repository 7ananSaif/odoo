import { KanbanRecord } from "@web/views/kanban/kanban_record";

export class AccountReturnKanbanRecord extends KanbanRecord {
    setup() {
        super.setup();
        if (this.props.record.data.activity_type_icon === 'fa-check') {
            this.props.record.data.activity_type_icon = 'fa-tasks';
        }
    }

    getRecordClasses() {
        let classes = super.getRecordClasses();
        // Remove the cursor on the card of the return when being on the checks kanban view
        if (this.props.record.context?.in_checks_view) {
            classes = classes.replace(/\bcursor-pointer\b/, "");
        }
        return classes;
    }
}
