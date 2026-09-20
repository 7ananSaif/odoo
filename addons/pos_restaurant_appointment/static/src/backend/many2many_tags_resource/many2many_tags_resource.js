import { registry } from "@web/core/registry";
import {
    Many2ManyTagsField,
    many2ManyTagsField,
} from "@web/views/fields/many2many_tags/many2many_tags_field";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { deserializeDateTime } from "@web/core/l10n/dates";

export class FieldMany2ManyTagsResourceMany2XAutocomplete extends Many2XAutocomplete {
    static template = "pos_restaurant_appointment.FieldMany2ManyTagsResourceMany2XAutocomplete";
    static components = {
        ...Many2XAutocomplete.components,
    };
    static props = {
        ...Many2XAutocomplete.props,
        event_start_time: { type: Object, optional: true },
        event_end_time: { type: Object, optional: true },
    };

    getPeopleCount(record) {
        if (record.is_used) {
            const localStartTime = deserializeDateTime(record.is_used.event_start);
            const localEndTime = deserializeDateTime(record.is_used.event_stop);
            const eventStart = this.props.event_start_time;
            const eventEnd = this.props.event_end_time;
            return localStartTime < eventEnd && localEndTime > eventStart
                ? record.is_used.capacity
                : "";
        }
        return "";
    }
}

export class FieldMany2ManyTagsResource extends Many2ManyTagsField {
    static template = "pos_restaurant_appointment.FieldMany2ManyTagsResource";
    static components = {
        ...Many2ManyTagsField.components,
        Many2XAutocomplete: FieldMany2ManyTagsResourceMany2XAutocomplete,
    };

    get context() {
        const context = this.props.context || {};
        const jsDate = this.props.record.data.start;
        context["start_date"] = jsDate ? jsDate.toFormat("yyyy-MM-dd HH:mm:ss") : null;
        return context;
    }

    get specification() {
        return {
            is_used: {},
        };
    }
}

export const fieldMany2ManyTagsResource = {
    ...many2ManyTagsField,
    component: FieldMany2ManyTagsResource,
};

registry.category("fields").add("many2many_tags_resource", fieldMany2ManyTagsResource);
