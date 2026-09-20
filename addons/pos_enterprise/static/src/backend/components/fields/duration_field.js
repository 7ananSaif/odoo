/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DurationField extends Component {
    static template = "pos_enterprise.DurationField";
    static props = {
        ...standardFieldProps,
        inputType: { type: String, optional: true },
    };

    static defaultProps = {
        inputType: "text",
    };

    setup() {
        this.inputRef = useInputField({
            getValue: () => this.displayValue,
            refName: "numpadDecimal",
        });
        useNumpadDecimal();
    }

    get displayValue() {
        const value = this.props.record.data[this.props.name];
        return formatDuration(value);
    }
}

export const durationField = {
    component: DurationField,
    displayName: _t("Duration"),
    supportedTypes: ["float", "integer"],
    isEmpty: () => false,
    extractProps: ({ options }) => ({
        inputType: options?.type || "text",
    }),
};

function formatDuration(value) {
    if (value == undefined || isNaN(value) || value < 0) {
        return "";
    }
    const duration = luxon.Duration.fromObject({ seconds: value });
    const formatted = duration.toFormat("d'd' h'h' m'm' s's'");
    return formatted.replace(/\b0[dhms]\b\s*/g, "").trim();
}

registry.category("fields").add("duration_time", durationField);
registry.category("formatters").add("duration_time", formatDuration);
