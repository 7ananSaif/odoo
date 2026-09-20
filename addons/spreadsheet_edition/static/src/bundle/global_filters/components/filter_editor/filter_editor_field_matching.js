import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";

import { Component } from "@odoo/owl";
import { FilterFieldOffset } from "../filter_field_offset";
import { sortModelFieldSelectorFields } from "../../../helpers/misc";

/**
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 */

export class FilterEditorFieldMatching extends Component {
    static template = "spreadsheet_edition.FilterEditorFieldMatching";
    static components = {
        ModelFieldSelector,
        FilterFieldOffset,
    };

    static props = {
        // See AbstractFilterEditorSidePanel fieldMatchings
        fieldMatchings: Array,
        selectField: Function,
        filterModelFieldSelectorField: Function,
        onOffsetSelected: { type: Function, optional: true },
    };

    sortModelFieldSelectorFields = sortModelFieldSelectorFields;

    /**
     *
     * @param {FieldMatching} fieldMatch
     * @returns {string}
     */
    getModelField(fieldMatch) {
        if (!fieldMatch || !fieldMatch.chain) {
            return "";
        }
        return fieldMatch.chain;
    }
}
