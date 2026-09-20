import { Component, onWillStart, useState } from "@odoo/owl";
import { components, stores } from "@odoo/o-spreadsheet";
import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";

import { FilterEditorStore } from "../../filter_editor_store";
import { FilterFieldOffset } from "../filter_field_offset";
import { sortModelFieldSelectorFields } from "../../../helpers/misc";

const { Section } = components;
const { useLocalStore } = stores;

export class RelatedFilters extends Component {
    static template = "spreadsheet_edition.RelatedFilters";

    static props = {
        resModel: String,
        dataSourceId: String,
        dataSourceType: String,
    };

    static components = { ModelFieldSelector, Section, FilterFieldOffset };

    setup() {
        this.sortModelFieldSelectorFields = sortModelFieldSelectorFields;
        this.editedFilters = useState({});
        this.stores = {};
        for (const filter of this.env.model.getters.getGlobalFilters()) {
            this.stores[filter.id] = useLocalStore(
                FilterEditorStore,
                { id: filter.id },
                filter.type
            );
            onWillStart(async () => {
                await this.stores[filter.id].loadData;
            });
        }
    }

    get canSave() {
        return Object.values(this.stores).every((store) => store.canSave);
    }

    getFieldMatching(filterId) {
        const fieldMatching = this.stores[filterId].fieldsMatching.find(
            (fieldMatching) =>
                fieldMatching.payload().id === this.props.dataSourceId &&
                fieldMatching.payload().type === this.props.dataSourceType
        );
        return fieldMatching;
    }

    filterModelFieldSelectorField(filterId, field, path, coModel) {
        return this.stores[filterId].filterModelFieldSelectorField(field, path, coModel);
    }

    updateFieldMatchingOffset(filterId, fieldMatchingId, offset) {
        this.stores[filterId].updateFieldMatchingOffset(fieldMatchingId, offset);
        this.save();
    }

    selectField(filterId, fieldMatchingId, path, field) {
        this.stores[filterId].updateFieldMatching(fieldMatchingId, path, field);
        this.save();
    }

    removeFieldMatching(filterId, fieldMatchingId) {
        this.stores[filterId].updateFieldMatching(fieldMatchingId, null);
        this.editedFilters[filterId] = false;
        this.save();
    }

    linkFieldMatching(filterId) {
        this.editedFilters[filterId] = true;
    }

    save() {
        if (!this.canSave) {
            return;
        }
        const fieldMatchings = {};
        for (const filterId in this.stores) {
            fieldMatchings[filterId] = this.getFieldMatching(filterId).fieldMatch;
        }
        this.env.model.dispatch("SET_DATASOURCE_FIELD_MATCHING", {
            dataSourceId: this.props.dataSourceId,
            fieldMatchings,
            dataSourceType: this.props.dataSourceType,
        });
    }
}
