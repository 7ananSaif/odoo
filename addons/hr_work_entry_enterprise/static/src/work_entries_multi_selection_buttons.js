import { WorkEntryCalendarMultiSelectionButtons } from "@hr_work_entry/views/work_entry_calendar/work_entry_multi_selection_buttons";

export class WorkEntriesMultiSelectionButtons extends WorkEntryCalendarMultiSelectionButtons {
    static template = "hr_work_entry_enterprise.WorkEntriesMultiSelectionButtons";
    static props = {
        reactive: {
            type: Object,
            shape: {
                ...WorkEntryCalendarMultiSelectionButtons.props.reactive.shape,
                onPlan: { type: Function, optional: true },
            },
        },
    };
    /**
     * @override
     */
    makeValues(workEntryTypeId) {
        const values = super.makeValues(workEntryTypeId);
        delete values.employee_id;
        return values;
    }
}
