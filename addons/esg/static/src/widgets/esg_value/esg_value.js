import { registry } from "@web/core/registry";
import { floatField, FloatField } from "@web/views/fields/float/float_field";

const fieldRegistry = registry.category("fields");

class ESGValue extends FloatField {
    static template = "esg.esgValue";
}

const esgValue = {
    ...floatField,
    component: ESGValue,
};

fieldRegistry.add("esg_value", esgValue);
