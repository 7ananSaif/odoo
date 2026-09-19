import { AiPrompt, AiPromptDialog } from "@ai/ai_prompt/ai_prompt";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { FieldProperties } from "@web_studio/client_action/view_editor/interactive_editor/properties/field_properties/field_properties";

Object.assign(FieldProperties.components, { AiPrompt });

// todo: ideally should apply them by default for ai fields
const aiWidgetForFieldType = {
    char: "ai_char",
    text: "ai_text",
    html: "ai_html",
    integer: "ai_integer",
    float: "ai_float",
    monetary: "ai_monetary",
    date: "ai_date",
    datetime: "ai_datetime",
    boolean: "ai_boolean",
    selection: "ai_selection",
    many2one: "ai_many2one",
    many2many: "ai_many2many_tags",
};

patch(FieldProperties.prototype, {
    get isAi() {
        return !!this.props.node.field.ai || this.props.node.field.ai === "";
    },

    async onChangeAi(value) {
        const field = this.props.node.field;
        await rpc("/web_studio/edit_field", {
            model_name: this.env.viewEditorModel.resModel,
            field_name: this.props.node.field.name,
            values: { ai: value },
        });
        field.ai = value && "";
        this.onChangeAttribute(value ? aiWidgetForFieldType[field.type] : "", "widget");
    },

    async updateSystemPrompt(value) {
        const field = this.props.node.field;
        await rpc("/web_studio/edit_field", {
            model_name: this.env.viewEditorModel.resModel,
            field_name: this.props.node.field.name,
            values: { system_prompt: value },
        });
        field.ai = value;
    },

    onSystemPromptClick() {
        if (!this.props.node.field.manual) {
            return;
        }
        this.dialog.add(AiPromptDialog, {
            aiPromptProps: {
                comodel: this.comodel,
                domain: this.props.node.attrs.domain || "",
                model: this.env.viewEditorModel.resModel,
                prompt: this.props.node.field.ai || "",
                readonly: false,
                aiFieldPath: this.props.node.field.name,
            },
            confirm: (newPrompt) => this.updateSystemPrompt(newPrompt),
        });
    },

    get comodel() {
        if (["many2one", "many2many"].includes(this.props.node.field.type)) {
            return this.props.node.field.relation;
        }
        return undefined;
    },
});
