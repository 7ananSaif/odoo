import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { NewFields } from "@web_studio/client_action/view_editor/editors/components/view_fields";
import { InteractiveEditor } from "@web_studio/client_action/view_editor/interactive_editor/interactive_editor";
import { AiFieldConfigurationDialog } from "@web_studio_ai_fields/client_action/view_editor/interactive_editor/field_configuration/ai_field_configuration_dialog";

patch(NewFields.prototype, {
    get newFieldsComponents() {
        return [
            ...super.newFieldsComponents,
            {
                classType: "ai",
                type: "AI",
                string: _t("AI Field"),
                name: "ai",
                dropData: JSON.stringify({ ai: true }),
            },
        ];
    },
});

patch(InteractiveEditor.prototype, {
    async getNewFieldNode(data) {
        if (!data.ai) {
            return super.getNewFieldNode(data);
        }
        return await new Promise((resolve) => {
            this.addDialog(AiFieldConfigurationDialog, {
                cancel: () => {},
                confirm: (nodeData) => resolve(nodeData),
                propertiesModel: this.env.viewEditorModel.resModel,
            });
        });
    },
});
