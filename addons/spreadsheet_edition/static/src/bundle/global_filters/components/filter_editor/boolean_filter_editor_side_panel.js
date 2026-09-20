/** @ts-check */

import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";

export class BooleanFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.BooleanFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
    };

    get type() {
        return "boolean";
    }

    getOperatorLabel(operator) {
        return operator ? getOperatorLabel(operator) : "";
    }

    updateBooleanDefaultValue(ev) {
        if (ev.target.value === "") {
            this.updateDefaultValue(undefined);
        } else {
            this.updateDefaultValue({ operator: ev.target.value });
        }
    }
}
