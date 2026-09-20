import { registry } from "@web/core/registry";
import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";
import { ListDateTimeField, listDateField } from "@web/views/fields/datetime/list_datetime_field";

export class EsgDateTimeField extends DateTimeField {
    static template = "esg.EsgDateTimeField";

    shouldShowSeparator() {
        return !this.isEmpty(this.endDateField) && super.shouldShowSeparator();
    }
}

export const esgDateRangeField = {
    ...dateField,
    component: EsgDateTimeField,
};

registry.category("fields").add("esg_daterange", esgDateRangeField);

export class EsgListDateTimeField extends ListDateTimeField {
    static template = "esg.EsgDateTimeField";

    shouldShowSeparator() {
        return !this.isEmpty(this.endDateField) && super.shouldShowSeparator();
    }
}

export const esgListDateRangeField = {
    ...listDateField,
    component: EsgListDateTimeField,
};

registry.category("fields").add("esg_list_daterange", esgListDateRangeField);
