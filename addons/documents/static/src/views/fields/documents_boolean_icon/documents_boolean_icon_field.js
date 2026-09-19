import { registry } from "@web/core/registry";
import {
    booleanIconField,
    BooleanIconField,
} from "@web/views/fields/boolean_icon/boolean_icon_field";

export class DocumentsBooleanIconField extends BooleanIconField {
    static template = "documents.DocumentsBooleanIconField";
    static props = {
        ...BooleanIconField.props,
        btnTrueClass: { type: String, optional: true },
        btnFalseClass: { type: String, optional: true },
    };
}

export const documentsBooleanIconField = {
    ...booleanIconField,
    component: DocumentsBooleanIconField,
    extractProps: (...args) => {
        const [{ options }] = args;
        return {
            ...booleanIconField.extractProps(...args),
            btnTrueClass: options.btn_true_class,
            btnFalseClass: options.btn_false_class,
        };
    },
};

registry.category("fields").add("documents_boolean_icon", documentsBooleanIconField);
