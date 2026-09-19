import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from '@web/views/fields/x2many/x2many_field';

import { TimesheetsListRenderer } from "./timesheets_list_renderer";

export class TimesheetIdsOne2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: TimesheetsListRenderer,
    }
}

export const timesheetIdsOne2ManyField = {
    ...x2ManyField,
    component: TimesheetIdsOne2ManyField,
}

registry.category("fields").add("timesheets_one2many", timesheetIdsOne2ManyField);
