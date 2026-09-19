/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

const WARNING_TYPE_ORDER = ["danger", "warning", "info"];

export class ActionableWarningsField extends Component {
    static template = "hr_payroll.ActionableWarnings";
    static props = {
        ...standardFieldProps,
        firstOnly: { type: Boolean, optional: true },
    };
    static defaultProps = { firstOnly: false };

    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    get errorData() {
        return this.props.record.data[this.props.name];
    }

    async handleOnClick(errorData){
        return this.actionService.doAction(errorData.action, {
            onClose: (onCloseInfo) =>  {
                if (!onCloseInfo?.noReload) {
                    this.env.model.load();
                }
            }
        });
    }

    get sortedActionableWarnings() {
        return this.errorData && Object.fromEntries(
            Object.entries(this.errorData).sort(
                (a, b) =>
                    WARNING_TYPE_ORDER.indexOf(b[1]["level"] || "warning") -
                    WARNING_TYPE_ORDER.indexOf(a[1]["level"] || "warning"),
            ),
        );
    }

    get warningsByLevel() {
        let result = {info: [], warning: [], danger: []};
        Object.entries(this.errorData).forEach(
            entry => {
                const [index, warning] = entry;
                warning.id = index;
                result[warning["level"]].push(warning);
            }
        );
        return result
    }

    get firstWarning() {
        // assume non-empty
        return Object.entries(this.errorData)[0][1];
    }
}

export const actionableWarningsField = {
    component: ActionableWarningsField,
    supportedOptions: [
        {
            label: _t("Display first warning only"),
            name: "first_only",
            type: "boolean",
        },
    ],
    extractProps({ options }) {
        return {
            firstOnly: options.first_only,
        };
    },
};
registry.category("fields").add("actionable_warnings", actionableWarningsField);
