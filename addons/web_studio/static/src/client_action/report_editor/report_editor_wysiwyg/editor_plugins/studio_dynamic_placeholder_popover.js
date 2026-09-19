import { Component, onWillStart, useState } from "@odoo/owl";
import { useService, useAutofocus } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";

export class StudioDynamicPlaceholderPopover extends Component {
    static template = "web_studio.StudioDynamicPlaceholderPopover";
    static components = { ModelFieldSelector };
    static props = {
        resModel: String,
        availableQwebVariables: Object,
        close: Function,
        validate: Function,
        initialQwebVar: String,
        showOnlyX2ManyFields: Boolean,
        initialPath: { optional: true },
        initialLabelValue: { optional: true },
    };

    static defaultProps = {
        initialPath: false,
        initialLabelValue: false,
    };

    setup() {
        useAutofocus();
        this.state = useState({
            currentVar: this.props.initialQwebVar,
            path: this.props.initialPath || "",
            isPathSelected: false,
            labelValue: this.props.initialLabelValue || null,
        });
        this.fieldService = useService("field");
        useHotkey("Enter", () => this.validate(), { bypassEditableProtection: true });
        useHotkey("Escape", () => this.props.close(), { bypassEditableProtection: true });

        onWillStart(async () => {
            if (this.state.path) {
                const fieldInfo = (
                    await this.fieldService.loadFieldInfo(this.currentResModel, this.state.path)
                ).fieldDef;
                this.fieldType = fieldInfo.type;
                this.state.fieldName = fieldInfo.string;
            }
        });
    }

    get labelValueInput() {
        const state = this.state;
        const lv = state.labelValue;
        return (lv !== null ? lv : state.fieldName) || "";
    }
    onLabelInput(ev) {
        const val = ev.target.value;
        this.state.labelValue = val;
    }

    filter(fieldDef) {
        if (this.props.showOnlyX2ManyFields) {
            return ["one2many", "many2many"].includes(fieldDef.type);
        } else {
            /**
             * We don't want to display x2many fields inside a report as it would not make sense.
             * We also don't want to display boolean fields.
             * This override is necessary because we want to be able to select non-searchable fields.
             * There is no reason as to why this wouldn't be allowed inside a report as we don't search on those fields,
             * we simply render them.
             */
            return !["one2many", "boolean", "many2many"].includes(fieldDef.type);
        }
    }

    async validate() {
        const resModel = this.currentResModel;
        const fieldInfo = (await this.fieldService.loadFieldInfo(resModel, this.state.path))
            .fieldDef;
        if (!fieldInfo) {
            return;
        }
        const filename_exists = (
            await this.fieldService.loadFieldInfo(resModel, this.state.path + "_filename")
        ).fieldDef;
        const is_image = fieldInfo.type == "binary" && !filename_exists;
        this.props.validate(
            this.state.currentVar,
            this.state.path,
            this.labelValueInput,
            is_image,
            fieldInfo.relation,
            fieldInfo.string
        );
        this.props.close();
    }

    setPath(path, { fieldDef }) {
        this.state.path = path;
        this.state.fieldName = fieldDef?.string;
        this.fieldType = fieldDef?.type;
    }

    get currentModel() {
        const currentVar = this.state.currentVar;
        const model = currentVar && this.props.availableQwebVariables[currentVar];
        return model || {};
    }

    get currentResModel() {
        const resModel = this.currentModel.model;
        return resModel || this.props.resModel;
    }
}
