import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { exprToBoolean } from "@web/core/utils/strings";

export class AccountAuditClickableCharField extends CharField {
    static template = "account_reports.AccountAuditClickableCharField";

    static props = {
        ...CharField.props,
        onclick: { type: String },
    };

    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async onClickField() {
        const test = {
            context: this.props.record.context,
            resModel: this.props.record.resModel,
            name: this.props.onclick,
            type: "object",
            resId: this.props.record.resId,
        };
        this.actionService.doActionButton(test);
    }
}

export const accountAuditClickableCharField = {
    ...charField,
    component: AccountAuditClickableCharField,
    supportedOptions: [
        {
            label: _t("Dynamic Placeholder"),
            name: "placeholder_field",
            type: "field",
            availableTypes: ["char", "text"],
            help: _t(
                "Displays the value of the selected field as a textual hint. If the selected field is empty, the static placeholder attribute is displayed instead."
            ),
        },
        {
            label: _t("OnClick Handler"),
            name: "onclick",
            type: "function",
            availableTypes: ["char", "text"],
            help: _t(
                "Name of the function to call when the cell value is clicked."
            ),
        },
    ],
    extractProps: ({ attrs, options, placeholder }) => ({
        isPassword: exprToBoolean(attrs.password),
        dynamicPlaceholder: options.dynamic_placeholder || false,
        dynamicPlaceholderModelReferenceField:
            options.dynamic_placeholder_model_reference_field || "",
        autocomplete: attrs.autocomplete,
        placeholder,
        onclick: options.onclick,
    }),
};

registry.category("fields").add("accountAuditClickableCharField", accountAuditClickableCharField);
