import { CalendarFilterSection } from "@web/views/calendar/calendar_filter_section/calendar_filter_section";

export class PlanningCalendarFilterSection extends CalendarFilterSection {

    static template = "planning.PlanningCalendarFilterSection";
    static subTemplates = {
        filter: "planning.PlanningCalendarFilterSection.filter",
    };

    getNoColor(filter) {
        return this.section.fieldName == 'resource_id' ? 'no_filter_color' : '';
    }

    /*
    * @override
    * By default, this function puts filter with empty value at the end of the list. In planning, we want it to be
    * the first filter displayed.
    */
    getSortedFilters() {
        let sortedFilters = super.getSortedFilters();
        let nullValueItem = false;
        for (const item of sortedFilters) {
            if (!item.value) {
                nullValueItem = item;
                break;
            }
        }
        if (nullValueItem) {
            sortedFilters.splice(sortedFilters.indexOf(nullValueItem), 1);
            sortedFilters.splice(0, 0, nullValueItem);
        }
        return sortedFilters;
    }

    /*
    * @override
    */
    async loadSource(request) {
        const searchReadIds = await this.orm.searchRead(
            'resource.resource',
            [['resource_type', '=', 'user']],
            ['id']
        );
        const humanResourceIds = searchReadIds.map(elem => elem.id)
        const options = await super.loadSource(request);
        for (const index in options) {
            if (humanResourceIds.includes(options[index].data?.id)) {
                options[index].data.isHumanResource = true;
            }
        }
        return options;
    }
}
