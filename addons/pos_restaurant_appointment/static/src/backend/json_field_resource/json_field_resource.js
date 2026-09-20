import { registry } from "@web/core/registry";
import { JsonField, jsonField } from "@web/views/fields/json/json_field";
import { deserializeDateTime } from "@web/core/l10n/dates";

export class JsonFieldResource extends JsonField {
    static template = "pos_restauramt_appointment.JsonFieldResource";

    get timeAndPersonDetails() {
        const formattedValue = JSON.parse(this.formattedValue || "{}");
        if (this.formattedValue) {
            // formattedValue.event_start is the start time in UTC
            const localStartTime = deserializeDateTime(formattedValue.event_start);
            return {
                time: localStartTime.toFormat("h:mm a"),
                person: formattedValue.capacity,
            };
        } else {
            return false;
        }
    }
}

export const jsonFieldResource = {
    ...jsonField,
    component: JsonFieldResource,
};

registry.category("fields").add("json_field_resource", jsonFieldResource);
