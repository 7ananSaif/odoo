import { binaryField, BinaryField } from "@web/views/fields/binary/binary_field";
import { registry } from "@web/core/registry";


export class PayRunBinaryField extends BinaryField {
    static template = "hr_payroll.PayRunBinaryField";
    static props = {
        ...BinaryField.props,
        formatField: { type: String, optional: true },
    };

    get format() {
        return this.props.record.data[this.props.formatField] || "";
    }
}

export const payRunBinaryField = {
    ...binaryField,
    component: PayRunBinaryField,
    extractProps: ({ attrs, options }) => {
        return {
            ...binaryField.extractProps({ attrs, options }),
            formatField: attrs.format,
        };
    }
};

registry.category("fields").add("payrun_binary", payRunBinaryField);
