import { KanbanRecord } from "@web/views/kanban/kanban_record";

export class AccountReturnCheckKanbanRecord extends KanbanRecord {
    onGlobalClick(ev, newWindow) {
        if (this.props.record.data.action)
            super.onGlobalClick(ev, newWindow);
    }

    getRecordClasses() {
        const { archInfo, forceGlobalClick } = this.props;
        let classes = super.getRecordClasses();

        const shouldHaveCursorPointer = (forceGlobalClick || archInfo.openAction || archInfo.canOpenRecords) && this.props.record.data.action;
        classes = classes.replace(/\bcursor-pointer\b/, "");

        if (shouldHaveCursorPointer) {
            classes += " cursor-pointer";
        }

        return classes.trim();
    }
} 
