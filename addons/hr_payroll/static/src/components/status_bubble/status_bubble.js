import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class StatusBubble extends Component {
    static template = "hr_payroll.StatusBubble";
    static props = {
        record: { type: Object },
        removeStates: { type: Array, optional: true },
    };
    static defaultProps = {
        removeStates: [],
    };

    setup() {
        this.props.issueCount = this.props.record.data['payslips_without_issues'];
        this.selection = this.props.record.fields.state.selection.filter(
            (o) => !this.props?.removeStates.includes(o[0])
        );
    }

    get hasError() {
        return this.props.record.data.has_error ?? false;
    }

    get issueCount() {
        return this.props.record.data.payslips_with_issues ?? 0;
    }

    get activeIndex() {
        return this.selection.findIndex(([key]) => key === this.props.record.data.state);
    }
}

export class StatusBubbleField extends StatusBubble {
    static props = { ...standardFieldProps, ...StatusBubble.props };
}

export const statusBubbleField = {
    component: StatusBubbleField,
    displayName: _t("Status Bubble"),
    supportedOptions: [
        {
            label: _t("Issue Count"),
            name: "issue_count_field",
            type: "integer",
        },
        {
            label: _t("Has Error"),
            name: "has_error_field",
            type: "boolean",
        },
        {
            label: _t("Remove State"),
            name: "remove_states",
            type: "string",
        },
    ],
    fieldDependencies: [
        { name: "payslips_with_issues", type: "integer"},
        { name: "has_error", type: "boolean"},
    ],
    supportedTypes: ["many2one", "selection"],
    extractProps({ options }) {
        return {
            removeStates: options.remove_states,
        };
    },
};

registry.category("fields").add("hr_payroll_status_bubble", statusBubbleField);
