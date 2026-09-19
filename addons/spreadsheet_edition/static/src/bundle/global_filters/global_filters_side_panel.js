import { FilterValue } from "@spreadsheet/global_filters/components/filter_value/filter_value";
import { _t } from "@web/core/l10n/translation";
import { Component, useRef } from "@odoo/owl";
import { hooks, components } from "@odoo/o-spreadsheet";
import { GlobalFilterSuggestions } from "./global_filter_suggestions/global_filter_suggestions";

const { Section } = components;

/**
 * This is the side panel to define/edit a global filter.
 * It can be of 3 different type: text, date and relation.
 */
export class GlobalFiltersSidePanel extends Component {
    static template = "spreadsheet_edition.GlobalFiltersSidePanel";
    static components = { FilterValue, GlobalFilterSuggestions, Section };
    static props = {
        onCloseSidePanel: { type: Function, optional: true },
    };

    dnd = hooks.useDragAndDropListItems();
    filtersListRef = useRef("filtersList");

    setup() {
        this.getters = this.env.model.getters;
    }

    get isReadonly() {
        return this.env.model.getters.isReadonly();
    }

    get filters() {
        return this.env.model.getters.getGlobalFilters();
    }

    _t(...args) {
        return _t(...args);
    }

    hasDataSources() {
        return (
            this.env.model.getters.getPivotIds().length +
            this.env.model.getters.getListIds().length +
            this.env.model.getters.getOdooChartIds().length
        );
    }

    newText() {
        this.env.replaceSidePanel("TEXT_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newSelection() {
        this.env.replaceSidePanel("SELECTION_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newDate() {
        this.env.replaceSidePanel("DATE_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newRelation() {
        this.env.replaceSidePanel("RELATION_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newBoolean() {
        this.env.replaceSidePanel("BOOLEAN_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newNumeric() {
        this.env.replaceSidePanel("NUMERIC_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    /**
     * @param {string} id
     */
    openEditor(id) {
        const filter = this.env.model.getters.getGlobalFilter(id);
        if (!filter) {
            return;
        }
        switch (filter.type) {
            case "text":
                this.env.replaceSidePanel("TEXT_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL", {
                    id,
                });
                break;
            case "date":
                this.env.replaceSidePanel("DATE_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL", {
                    id,
                });
                break;
            case "relation":
                this.env.replaceSidePanel(
                    "RELATION_FILTER_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "boolean":
                this.env.replaceSidePanel(
                    "BOOLEAN_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "selection":
                this.env.replaceSidePanel(
                    "SELECTION_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "numeric":
                this.env.replaceSidePanel(
                    "NUMERIC_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
        }
    }

    startDragAndDrop(filter, event) {
        if (event.button !== 0) {
            return;
        }

        const rects = this.getFiltersElementsRects();
        const filtersItems = this.filters.map((filter, index) => ({
            id: filter.id,
            size: rects[index].height,
            position: rects[index].y,
        }));
        this.dnd.start("vertical", {
            draggedItemId: filter.id,
            initialMousePosition: event.clientY,
            items: filtersItems,
            scrollableContainerEl: this.filtersListRef.el,
            onDragEnd: (filterId, finalIndex) => this.onDragEnd(filterId, finalIndex),
        });
    }

    getFiltersElementsRects() {
        return Array.from(this.filtersListRef.el.children[0].children).map((filterEl) =>
            filterEl.getBoundingClientRect()
        );
    }

    getFilterItemStyle(filter) {
        return this.dnd.itemsStyle[filter.id] || "";
    }

    setGlobalFilterValue(id, value, displayNames) {
        this.env.model.dispatch("SET_GLOBAL_FILTER_VALUE", {
            id,
            value,
            displayNames,
        });
    }

    onDragEnd(filterId, finalIndex) {
        const originalIndex = this.filters.findIndex((filter) => filter.id === filterId);
        const delta = finalIndex - originalIndex;
        if (filterId && delta !== 0) {
            this.env.model.dispatch("MOVE_GLOBAL_FILTER", {
                id: filterId,
                delta,
            });
        }
    }

    deleteFilter(filterId) {
        this.env.model.dispatch("REMOVE_GLOBAL_FILTER", { id: filterId });
    }
}
