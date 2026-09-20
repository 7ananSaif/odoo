import { registry } from "@web/core/registry";
import {
    listDateTimeField,
    ListDateTimeField,
} from "@web/views/fields/datetime/list_datetime_field";
import { formatFloatTime } from "@web/views/fields/formatters";

export class PlannedDateRangeWithAllocatedHours extends ListDateTimeField {
    static template = "planning.PlannedDateRangeWithAllocatedHours";

    get allocatedHoursFormatted() {
        return formatFloatTime(this.props.record.data.allocated_hours);
    }
}

export const plannedDateRangeWithAllocatedHours = {
    ...listDateTimeField,
    component: PlannedDateRangeWithAllocatedHours,
    fieldDependencies: [{ name: "allocated_hours", type: "float" }],
};

registry
    .category("fields")
    .add("planned_date_range_with_allocated_hours", plannedDateRangeWithAllocatedHours);
