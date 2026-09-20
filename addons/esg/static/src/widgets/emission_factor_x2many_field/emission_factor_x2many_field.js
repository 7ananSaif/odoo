import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

import { EmissionFactorListRenderer } from "./emission_factor_list_renderer";

export class EmissionFactorX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: EmissionFactorListRenderer,
    };
}

registry.category("fields").add("emission_factor_x2many", {
    ...x2ManyField,
    component: EmissionFactorX2ManyField,
});
