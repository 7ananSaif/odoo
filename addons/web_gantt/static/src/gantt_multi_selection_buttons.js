import { MultiSelectionButtons } from "@web/views/view_components/multi_selection_buttons";

export class GanttMultiSelectionButtons extends MultiSelectionButtons {
    static template = "web_gantt.GanttMultiSelectionButtons";
    static props = {
        reactive: {
            type: Object,
            shape: {
                ...MultiSelectionButtons.props.reactive.shape,
                onPlan: { type: Function, optional: true },
            },
        },
    };
}
