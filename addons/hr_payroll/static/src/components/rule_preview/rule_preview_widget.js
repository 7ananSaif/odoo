import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class RulePreviewWidget extends Component {
    static props = { ...standardFieldProps };
    static template = "hr_payroll.RulePreviewWidget";

    get text() {
        const { name: fieldName, record } = this.props;
        return record.data[fieldName] || "";;
    }

    get style() {
        const { color } = this.props.record.data;
        return color ? `color: ${color};` : "";
    }

    get classes() {
        const data = this.props.record.data;
        let classes = [];

        if (data.bold) classes.push("fw-bold");
        if (data.italic) classes.push("fst-italic");
        if (data.underline) classes.push("text-decoration-underline");

        return classes.join(" ");
    }
}

export const rulePreviewWidget = {
    component: RulePreviewWidget
}

registry.category("fields").add("formatted_text_preview", rulePreviewWidget);
