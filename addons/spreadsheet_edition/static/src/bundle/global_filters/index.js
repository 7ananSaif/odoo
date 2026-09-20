import { _t } from "@web/core/l10n/translation";

import * as spreadsheet from "@odoo/o-spreadsheet";

import {
    SET_FILTER_MATCHING,
    SET_FILTER_MATCHING_CONDITION,
} from "@spreadsheet/pivot/pivot_actions";

import { GlobalFiltersSidePanel } from "./global_filters_side_panel";
import { FilterComponent } from "./filter_component";

import "./operational_transform";
import { DateFilterEditorSidePanel } from "./components/filter_editor/date_filter_editor_side_panel";
import { TextFilterEditorSidePanel } from "./components/filter_editor/text_filter_editor_side_panel";
import { RelationFilterEditorSidePanel } from "./components/filter_editor/relation_filter_editor_side_panel";
import { BooleanFilterEditorSidePanel } from "./components/filter_editor/boolean_filter_editor_side_panel";
import { SelectionFilterEditorSidePanel } from "./components/filter_editor/selection_filter_editor_side_panel";
import { NumericFilterEditorSidePanel } from "./components/filter_editor/numeric_filter_editor_side_panel";

const { sidePanelRegistry, topbarComponentRegistry, cellMenuRegistry } = spreadsheet.registries;

sidePanelRegistry.add("DATE_FILTER_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: DateFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `DateFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("TEXT_FILTER_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: TextFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `TextFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("SELECTION_FILTERS_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: SelectionFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `SelectionFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("RELATION_FILTER_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: RelationFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `RelationFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("BOOLEAN_FILTERS_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: BooleanFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `BooleanFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("NUMERIC_FILTERS_SIDE_PANEL", {
    title: _t("Filter properties"),
    Body: NumericFilterEditorSidePanel,
    computeState: (getters, props) => ({
        isOpen: true,
        props,
        key: `NumericFilterEditorSidePanel_${props.id}`,
    }),
});

sidePanelRegistry.add("GLOBAL_FILTERS_SIDE_PANEL", {
    title: _t("Filters"),
    Body: GlobalFiltersSidePanel,
});

topbarComponentRegistry.add("filter_component", {
    component: FilterComponent,
    isVisible: (env) =>
        !env.model.getters.isReadonly() || env.model.getters.getGlobalFilters().length,
    sequence: 30,
});

cellMenuRegistry.add("use_global_filter", {
    name: _t("Set as filter"),
    sequence: 175,
    execute(env) {
        const position = env.model.getters.getActivePosition();
        SET_FILTER_MATCHING(position, env);
    },
    isVisible: (env) => {
        const position = env.model.getters.getActivePosition();
        return SET_FILTER_MATCHING_CONDITION(position, env.model.getters);
    },
    icon: "o-spreadsheet-Icon.SEARCH",
});
