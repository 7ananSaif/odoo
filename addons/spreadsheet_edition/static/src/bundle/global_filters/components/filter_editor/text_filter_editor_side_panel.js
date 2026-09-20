/** @ts-check */

import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { TextFilterValue } from "@spreadsheet/global_filters/components/filter_text_value/filter_text_value";

import { components } from "@odoo/o-spreadsheet";
import { useState } from "@odoo/owl";

const { SelectionInput } = components;

/**
 * This is the side panel to define/edit a global filter of type "text".
 */
export class TextFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.TextFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
        TextFilterValue,
        SelectionInput,
    };

    setup() {
        super.setup();
        this.state = useState({
            rangeRestriction: !!this.store.filter.rangesOfAllowedValues,
        });
    }

    get type() {
        return "text";
    }

    /**
     * @param {string[]} strings
     */
    updateTextDefaultValue(strings) {
        super.updateDefaultValue({ strings, operator: "ilike" });
    }

    toggleRangeRestriction(isChecked) {
        if (!isChecked) {
            this.onRangeChanged([]);
            this.store.update({ rangesOfAllowedValues: undefined });
        }
        this.state.rangeRestriction = isChecked;
    }

    onRangeChanged(ranges) {
        this.ranges = ranges;
    }

    onRangeConfirmed() {
        if (this.state.rangeRestriction && this.ranges.length) {
            const sheetId = this.env.model.getters.getActiveSheetId();
            const rangesOfAllowedValues = this.ranges.map((range) =>
                this.env.model.getters.getRangeFromSheetXC(sheetId, range)
            );
            this.ranges = [];
            this.store.update({ rangesOfAllowedValues });
        }
    }
}
