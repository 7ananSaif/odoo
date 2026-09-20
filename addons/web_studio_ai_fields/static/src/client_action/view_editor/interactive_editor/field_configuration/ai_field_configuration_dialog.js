import { AiPrompt } from "@ai/ai_prompt/ai_prompt";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { useService } from "@web/core/utils/hooks";
import { DynamicPlaceholderPopover } from "@web/views/fields/dynamic_placeholder_popover";
import { randomName } from "@web_studio/client_action/view_editor/editors/utils";
import { SelectionContentDialog } from "@web_studio/client_action/view_editor/interactive_editor/field_configuration/selection_content_dialog";

import { Component, useState } from "@odoo/owl";

export class AiFieldConfigurationDialog extends Component {
    static template = "web_studio_ai_fields.AiFieldConfigurationDialog";
    static components = { AiPrompt, Dialog, RecordSelector, SelectMenu };
    static props = {
        cancel: { type: Function },
        close: { type: Function },
        confirm: { type: Function },
        propertiesModel: { type: String },
        title: { type: String, optional: true },
    };

    setup() {
        this.popover = usePopover(DynamicPlaceholderPopover);
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.state = useState({
            fieldType: "char",
            prompt: "",
            relationId: false,
            relationName: false,
            selection: [],
            showMissingRelationWarning: false,
        });
    }

    get choices() {
        return Object.entries(this.fields).map(([key, field]) => ({ value: key, ...field }));
    }

    get fields() {
        return {
            char: {
                type: "char",
                label: _t("Text"),
                description: _t("New AI Text"),
                widget: "ai_char",
            },
            text: {
                type: "text",
                label: _t("Multiline Text"),
                description: _t("New AI Multiline Text"),
                widget: "ai_text",
            },
            html: {
                type: "html",
                label: _t("HTML"),
                description: _t("New AI HTML"),
                widget: "ai_html",
            },
            int: {
                type: "integer",
                label: _t("Integer"),
                description: _t("New AI Integer"),
                widget: "ai_integer",
            },
            float: {
                type: "float",
                label: _t("Decimal"),
                description: _t("New AI Decimal"),
                widget: "ai_float",
            },
            monetary: {
                type: "monetary",
                label: _t("Monetary"),
                description: _t("New AI Monetary"),
                widget: "ai_monetary",
            },
            date: {
                type: "date",
                label: _t("Date"),
                description: _t("New AI Date"),
                widget: "ai_date",
            },
            datetime: {
                type: "datetime",
                label: _t("Datetime"),
                description: _t("New AI Datetime"),
                widget: "ai_datetime",
            },
            bool: {
                type: "boolean",
                label: _t("Checkbox"),
                description: _t("New AI CheckBox"),
                widget: "ai_boolean",
            },
            selection: {
                type: "selection",
                label: _t("Selection"),
                description: _t("New AI Selection"),
                widget: "ai_selection",
            },
            m2o: {
                type: "many2one",
                label: _t("Many2one"),
                description: _t("New AI Many2One"),
                widget: "ai_many2one",
            },
            m2m: {
                type: "many2many",
                label: _t("Tags"),
                description: _t("New AI Tags"),
                widget: "ai_many2many_tags",
                icon: "tags",
            },
        };
    }

    get relation() {
        return this.state.relationName || undefined;
    }

    get relationSelectorProps() {
        return {
            resModel: "ir.model",
            domain: [
                ["transient", "=", false],
                ["abstract", "=", false],
            ],
            resId: this.state.relationId,
            update: async (resId) => {
                this.state.relationId = resId;
                this.state.relationName = resId && (await this.getRelationName(resId));
                if (resId) {
                    this.state.showMissingRelationWarning = false;
                }
            },
        };
    }

    get selectedField() {
        return this.fields[this.state.fieldType];
    }

    editSelection() {
        this.dialog.add(SelectionContentDialog, {
            defaultChoices: this.state.selection,
            onConfirm: (selection) => (this.state.selection = selection),
        });
    }

    async getRelationName(resId) {
        const [{ model }] = await this.orm.read("ir.model", [resId], ["model"]);
        return model;
    }

    async onConfirm() {
        if (["m2o", "m2m"].includes(this.state.fieldType) && !this.state.relationId) {
            this.state.showMissingRelationWarning = true;
            return;
        }
        const newNode = {
            field_description: {
                field_description: this.selectedField.description,
                model_name: this.props.propertiesModel,
                name: randomName(`x_studio_${this.selectedField.type}_field`),
                type: this.selectedField.type,
                ai: true,
                system_prompt: this.state.prompt,
            },
            tag: "field",
            attrs: { widget: this.selectedField.widget },
        };
        if (this.state.fieldType === "selection") {
            newNode.field_description.selection = this.state.selection;
        }
        if (["m2o", "m2m"].includes(this.state.fieldType)) {
            newNode.field_description.relation_id = this.state.relationId;
        }
        this.props.confirm(newNode);
        this.props.close();
    }
}
