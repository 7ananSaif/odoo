/** @ts-check */

import { ModelSelector } from "@web/core/model_selector/model_selector";
import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { useService } from "@web/core/utils/hooks";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { components } from "@odoo/o-spreadsheet";

import { useState, onWillStart } from "@odoo/owl";
import { SidePanelDomain } from "../../../components/side_panel_domain/side_panel_domain";

const { ValidationMessages } = components;

/**
 * @typedef {import("@spreadsheet").OdooField} OdooField
 * @typedef {import("@spreadsheet").GlobalFilter} GlobalFilter
 */

/**
 * This is the side panel to define/edit a global filter of type "relation".
 */
export class RelationFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.RelationFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        ModelSelector,
        MultiRecordSelector,
        FilterEditorFieldMatching,
        SidePanelDomain,
        ValidationMessages,
    };
    static props = {
        ...AbstractFilterEditorSidePanel.props,
        modelName: { type: String, optional: true },
        modelDisplayName: { type: String, optional: true },
    };
    setup() {
        super.setup();

        this.state = useState({
            domainRestriction: this.store.filter.domainOfAllowedValues?.length > 0,
        });

        this.nameService = useService("name");
        this.orm = useService("orm");
        onWillStart(this.onWillStart);
    }

    get type() {
        return "relation";
    }

    get missingModel() {
        return !this.store.filter.modelName;
    }

    async onWillStart() {
        await this.fetchRelationModelLabel();
    }

    async onModelSelected({ technical, label }) {
        this.store.selectRelatedModel(technical, label);
    }

    async fetchRelationModelLabel() {
        if (!this.store.filter.modelName) {
            return;
        }
        const result = await this.orm
            .cache({ type: "disk" })
            .call("ir.model", "display_name_for", [[this.store.filter.modelName]]);
        const label = result[0]?.display_name;
        this.store.updateRelationModelLabel(label);
        if (!this.store.filter.label) {
            this.store.update({ label });
        }
    }

    /**
     * @param {Number[]} resIds
     */
    async onValuesSelected(resIds) {
        const displayNames = await this.nameService.loadDisplayNames(
            this.store.filter.modelName,
            resIds
        );
        if (!resIds.length) {
            // force clear, even automatic default values
            this.store.update({ defaultValue: undefined });
        } else {
            this.store.update({
                defaultValue: {
                    operator: this.store.filter.defaultValue?.operator ?? "in",
                    ids: resIds,
                },
                displayNames: Object.values(displayNames),
            });
        }
    }

    toggleDefaultsToCurrentUser(checked) {
        if (checked) {
            this.store.update({ defaultValue: { operator: "in", ids: "current_user" } });
        } else {
            this.store.update({ defaultValue: undefined });
        }
    }
    toggleDomainRestriction(isChecked) {
        if (!isChecked) {
            this.onDomainUpdate([]);
        }
        this.state.domainRestriction = isChecked;
    }

    onDomainUpdate(domainOfAllowedValues) {
        this.store.update({ domainOfAllowedValues });
    }
}
