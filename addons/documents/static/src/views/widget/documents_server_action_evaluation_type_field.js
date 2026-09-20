import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class DocumentsServerActionEvaluationTypeField extends SelectionField {
    get options() {
        const optionLabel = _t("Change");
        return [
            ["value", optionLabel],
            ...this.props.record.fields[this.props.name].selection.filter(
                (option) => option[0] !== "value"
            ),
        ];
    }
}

export const documentsServerActionEvaluationTypeField = {
    ...selectionField,
    component: DocumentsServerActionEvaluationTypeField,
    displayName: _t("Evaluation type field for Documents server actions"),
    supportedTypes: ["selection"],
};

registry
    .category("fields")
    .add("documents_server_action_evaluation_type_field", documentsServerActionEvaluationTypeField);
