/** @ts-check */

import { stores, components } from "@odoo/o-spreadsheet";
import { onWillStart, Component } from "@odoo/owl";
import { FilterEditorStore } from "../../filter_editor_store";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { GlobalFilterFooter } from "../global_filter_footer/global_filter_footer";
import { _t } from "@web/core/l10n/translation";

const { Checkbox, Section, SidePanelCollapsible, TextInput, ValidationMessages } = components;
const { useLocalStore } = stores;

/**
 * @typedef {import("@spreadsheet").OdooField} OdooField
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 * @typedef {import("@spreadsheet").GlobalFilter} GlobalFilter
 *
 * @typedef State
 * @property {boolean} saved
 * @property {string} label label of the filter
 */

/**
 * This is the side panel to define/edit a global filter.
 * It can be of 3 different type: text, date and relation.
 */
export class AbstractFilterEditorSidePanel extends Component {
    static template = "";
    static components = {
        SidePanelCollapsible,
        Checkbox,
        Section,
        TextInput,
        FilterEditorFieldMatching,
        GlobalFilterFooter,
        ValidationMessages,
    };
    static props = {
        id: { type: String, optional: true },
        label: { type: String, optional: true },
        fieldMatching: { type: Object, optional: true },
        onCloseSidePanel: { type: Function, optional: true },
    };

    setup() {
        this.store = useLocalStore(FilterEditorStore, this.props, this.type);
        onWillStart(async () => await this.store.loadData);
    }

    get type() {
        throw new Error("Not implemented by children");
    }

    /**
     * @param {String} label
     */
    setLabel(label) {
        this.store.update({ label });
    }

    updateDefaultValue(defaultValue) {
        if (Array.isArray(defaultValue) && defaultValue.length === 0) {
            this.store.update({ defaultValue: undefined });
        } else {
            this.store.update({ defaultValue });
        }
    }

    get footerProps() {
        return {
            onClickSave: !this.store.isValid
                ? undefined
                : () => {
                      const sourcePanel = `${this.constructor.name}_${this.props.id}`;
                      this.store.saveGlobalFilter(sourcePanel);
                  },
            onClickDelete: !this.props.id
                ? undefined
                : () => {
                      if (this.props.id) {
                          this.env.model.dispatch("REMOVE_GLOBAL_FILTER", { id: this.props.id });
                      }
                      this.env.replaceSidePanel(
                          "GLOBAL_FILTERS_SIDE_PANEL",
                          `${this.constructor.name}_${this.props.id}`
                      );
                  },
            onClickCancel: () => {
                this.env.replaceSidePanel(
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    `${this.constructor.name}_${this.props.id}`
                );
            },
        };
    }

    get invalidModel() {
        return _t(
            "At least one data source has an invalid model. Please delete it before editing this global filter."
        );
    }
}
