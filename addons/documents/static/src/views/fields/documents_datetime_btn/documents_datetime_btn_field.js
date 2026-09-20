import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { deserializeDateTime, today } from "@web/core/l10n/dates";
import { user } from "@web/core/user";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsDatetimeBtnField extends Component {
    static template = "documents.DocumentsDatetimeBtnField";
    static props = {
        ...standardFieldProps,
        label: { type: String, optional: true },
        btnClasses: { type: String, optional: true },
        icon: { type: String, optional: true },
    };

    setup() {
        const pickerProps = {
            minDate: luxon.DateTime.now(),
            type: "datetime",
            value: this.props.record[this.props.name]
                ? deserializeDateTime(this.props.record[this.props.name], {
                      tz: user.context.tz,
                  })
                : today(),
        };
        this.dateTimePicker = useDateTimePicker({
            target: "datetime-btn",
            onApply: (date) => {
                this.props.record.update({ [this.props.name]: date });
            },
            get pickerProps() {
                return pickerProps;
            },
        });
    }
}

export const documentsDatetimeBtnField = {
    component: DocumentsDatetimeBtnField,
    supportedTypes: ["datetime"],
    extractProps: ({ string, options }) => ({
        btnClasses: options.btn_classes,
        label: string,
        icon: options.icon,
    }),
};

registry.category("fields").add("documents_datetime_btn", documentsDatetimeBtnField);
