import { CalendarSidePanel } from "@web/views/calendar/calendar_side_panel/calendar_side_panel";
import { PlanningCalendarFilterSection } from "../planning_filter_section/planning_calendar_filter_section";

export class PlanningCalendarSidePanel extends CalendarSidePanel {
    static template = "planning.PlanningCalendarSidePanel";
    static components = {
        ...CalendarSidePanel.components,
        FilterSection: PlanningCalendarFilterSection,
    };

    // overwrite to allow the display of the datepicker when a mode other than 'filter' was selected in the month scale
    get showDatePicker() {
        return (this.props.model.showDatePicker && !this.env.isSmall &&
            (this.props.model.meta.scale !== 'month' || this.props.mode === 'FILTER'));
    }
}
