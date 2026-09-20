import { beforeEach, describe, expect, getFixture, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import { helpers, stores } from "@odoo/o-spreadsheet";
import {
    addGlobalFilter,
    addGlobalFilterWithoutReload,
    createSheet,
    selectCell,
    setCellContent,
} from "@spreadsheet/../tests/helpers/commands";
import {
    defineSpreadsheetModels,
    getBasicData,
    getBasicPivotArch,
    getBasicServerData,
    IrModel,
    Partner,
} from "@spreadsheet/../tests/helpers/data";
import { assertDateDomainEqual } from "@spreadsheet/../tests/helpers/date_domain";
import { getCellValue } from "@spreadsheet/../tests/helpers/getters";
import { THIS_YEAR_GLOBAL_FILTER } from "@spreadsheet/../tests/helpers/global_filter";
import {
    createSpreadsheetWithList,
    insertListInSpreadsheet,
} from "@spreadsheet/../tests/helpers/list";
import {
    createSpreadsheetWithPivot,
    insertPivotInSpreadsheet,
} from "@spreadsheet/../tests/helpers/pivot";
import { toRangeData } from "@spreadsheet/../tests/helpers/zones";
import * as domainHelpers from "@web/../tests/core/tree_editor/condition_tree_editor_test_helpers";
import {
    contains,
    defineModels,
    fields,
    makeServerError,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";

import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";
import {
    createSpreadsheetWithChart,
    insertChartInSpreadsheet,
} from "@spreadsheet/../tests/helpers/chart";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { BooleanFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/boolean_filter_editor_side_panel";
import { DateFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/date_filter_editor_side_panel";
import { RelationFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/relation_filter_editor_side_panel";
import { TextFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/text_filter_editor_side_panel";
import { NumericFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/numeric_filter_editor_side_panel";
import { user } from "@web/core/user";
import { SelectionFilterEditorSidePanel } from "@spreadsheet_edition/bundle/global_filters/components/filter_editor/selection_filter_editor_side_panel";

const { useStoreProvider, ModelStore, NotificationStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

const { toZone } = helpers;

/**
 * @typedef {import("@spreadsheet").FixedPeriodDateGlobalFilter} FixedPeriodDateGlobalFilter
 */

let target;
class Vehicle extends models.Model {
    _name = "vehicle";
}

class Computer extends models.Model {
    _name = "computer";
}

const SIDE_PANELS = {
    text: TextFilterEditorSidePanel,
    date: DateFilterEditorSidePanel,
    relation: RelationFilterEditorSidePanel,
    boolean: BooleanFilterEditorSidePanel,
    selection: SelectionFilterEditorSidePanel,
    numeric: NumericFilterEditorSidePanel,
};

class Parent extends Component {
    static template = xml`<t t-component="comp" id='props.filterId'/>`;
    static props = {
        filterId: { type: String, optional: true },
        type: { type: String, optional: true },
        model: Object,
        notificationStore: { type: Object, optional: true },
    };

    get type() {
        if (this.props.filterId) {
            const filter = this.props.model.getters.getGlobalFilter(this.props.filterId);
            return filter.type;
        }
        return this.props.type;
    }

    get comp() {
        return SIDE_PANELS[this.type];
    }

    setup() {
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.props.model);
        if (this.props.notificationStore) {
            stores.inject(NotificationStore, this.props.notificationStore);
        }

        onMounted(() => {
            stores.on("store-updated", this, this.render.bind(this, true));
        });
        onWillUnmount(() => {
            stores.off("store-updated", this);
        });
    }
}

async function openSidePanelForCreation(model, env, type, notificationStore) {
    env.openSidePanel = env.openSidePanel ?? (() => {});
    return await mountWithCleanup(Parent, { env, props: { model, type, notificationStore } });
}

async function openSidePanel(model, env, filterId, notificationStore) {
    env.openSidePanel = env.openSidePanel ?? (() => {});
    await mountWithCleanup(Parent, { env, props: { model, filterId, notificationStore } });
}

async function selectModelForRelation(relation) {
    await contains('.o_side_panel_related_model input[type="text"]').click();
    await contains(`.o_model_selector_${relation.replaceAll(".", "_")}`).click();
}

async function selectModelForSelection(selection) {
    await contains('.o-selection-model-field input[type="text"]').click();
    await contains(`.o_model_selector_${selection.replaceAll(".", "_")}`).click();
}

async function selectFieldForSelection(fieldName) {
    await contains(".o_model_field_selector_value").click();
    await contains(`.o_model_field_selector_popover_item[data-name='${fieldName}'] button`).click();
}

async function selectFieldMatching(fieldName, fieldMatching = target) {
    // skipVisibilityCheck because the section is collapsible, which we don't care about in the tests
    await contains(fieldMatching.querySelector(".o_model_field_selector"), {
        visible: false,
    }).click();
    // We use `target` here because the popover is not in fieldMatching
    await contains(`.o_model_field_selector_popover_item[data-name='${fieldName}'] button`).click();
}

async function saveGlobalFilter() {
    await contains(".o_global_filter_save").click();
}

async function editGlobalFilterLabel(label) {
    const input = await contains(".o_global_filter_label");
    await input.click();
    await input.edit(label);
}

async function editGlobalFilterDefaultValue(defaultValue) {
    await contains(".o-global-filter-text-value input").edit(defaultValue);
}

beforeEach(() => {
    target = getFixture();
});

test("Pivot display name is displayed in field matching", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    model.dispatch("RENAME_PIVOT", { pivotId, name: "Hello" });
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "date",
        label: "This year",
    });
    await openSidePanel(model, env, "42");
    const name = target.querySelector(".o_spreadsheet_field_matching .fw-medium").innerText;
    expect(name).toBe("Hello");
});

test("List display name is displayed in field matching", async function () {
    const { model, env } = await createSpreadsheetWithList();
    const [listId] = model.getters.getListIds();
    model.dispatch("RENAME_ODOO_LIST", { listId, name: "Hello" });
    await addGlobalFilter(model, {
        id: "42",
        type: "date",
        label: "This year",
    });

    await openSidePanel(model, env, "42");
    const name = target.querySelector(".o_spreadsheet_field_matching .fw-medium").innerText;
    expect(name).toBe("Hello");
});

test("Create a new boolean global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "boolean");
    await editGlobalFilterLabel("My Label");
    await selectFieldMatching("active");
    expect(".o_filter_field_offset").toHaveCount(0, {
        message: "No offset for boolean filter",
    });
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
});

test("Create a new selection global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "selection");
    await editGlobalFilterLabel("My Label");
    await selectModelForSelection("res.users");
    await selectFieldForSelection("state");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.resModel).toBe("res.users");
    expect(globalFilter.selectionField).toBe("state");
});

test("Cannot save a selection filter without model-field", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "selection");
    await editGlobalFilterLabel("My Label");
    await saveGlobalFilter();
    expect(model.getters.getGlobalFilters()).toHaveLength(0);
    await selectModelForSelection("res.users");
    await saveGlobalFilter();
    expect(model.getters.getGlobalFilters()).toHaveLength(0);
    await selectFieldForSelection("state");
    await saveGlobalFilter();
    expect(model.getters.getGlobalFilters()).toHaveLength(1);
});

test("Selecting a model-field for selection will set the label if empty", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "selection");
    await selectModelForSelection("res.users");
    await selectFieldForSelection("state");
    expect(".o_global_filter_label").toHaveValue("Status (Users)");
});

test("Selecting a model-field for selection does not reset label", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "selection");
    await editGlobalFilterLabel("My Label");
    await selectModelForSelection("res.users");
    await selectFieldForSelection("state");
    expect(".o_global_filter_label").toHaveValue("My Label");
});

test("can select a default value for selection filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "selection");
    await selectModelForSelection("res.users");
    await selectFieldForSelection("state");
    await contains(".o-global-filter-selection-value input").click();
    await contains(".o-autocomplete .dropdown-item").click();
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.defaultValue).toEqual({ operator: "in", selectionValues: ["new"] });
});

test("Selecting another model resets the default value", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "selection",
        label: "Status",
        resModel: "res.users",
        selectionField: "state",
        defaultValue: { operator: "in", selectionValues: ["new"] },
    });
    await openSidePanel(model, env, "42");
    await openSidePanelForCreation(model, env, "selection");
    expect(".o_tag_badge_text").toHaveCount(1);
    await selectModelForSelection("partner");
    expect(".o_tag_badge_text").toHaveCount(0);
});

test("Selecting another field resets the default value", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "selection",
        label: "Status",
        resModel: "res.users",
        selectionField: "state",
        defaultValue: { operator: "in", selectionValues: ["new"] },
    });
    await openSidePanel(model, env, "42");
    await openSidePanelForCreation(model, env, "selection");
    expect(".o_tag_badge_text").toHaveCount(1);
    await selectFieldForSelection("lang");
    expect(".o_tag_badge_text").toHaveCount(0);
});

test("Create a new numeric global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "numeric");
    await editGlobalFilterLabel("My Label");
    await selectFieldMatching("probability");
    expect(".o_filter_field_offset").toHaveCount(0, {
        message: "No offset for numeric filter",
    });
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.type).toBe("numeric");
});

test("Create a new text global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await editGlobalFilterDefaultValue("Default Value");
    await selectFieldMatching("name");
    expect(".o_filter_field_offset").toHaveCount(0, {
        message: "No offset for text filter",
    });
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.defaultValue).toEqual({ operator: "ilike", strings: ["Default Value"] });
    expect(globalFilter.rangesOfAllowedValues).toBe(undefined);
});

test("Create a new text global filter with a range", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await contains(".restrict_to_range input[type=checkbox]").click();
    selectCell(model, "B1");
    await animationFrame();
    await contains(".o-selection-ok").click();
    expect(".o-selection-input input").toHaveValue("B1");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.rangesOfAllowedValues.length).toBe(1);
    expect(globalFilter.rangesOfAllowedValues[0].zone).toEqual(toZone("B1"));
});

test("Create a new text global filter with a default value from a range", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    setCellContent(model, "B1", "hello");
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await contains(".restrict_to_range input[type=checkbox]").click();
    selectCell(model, "B1");
    await animationFrame();
    await animationFrame(); // SelectionInput component needs an extra tick to update
    await contains(".o-selection-ok").click();
    await contains(".o-autocomplete input").click();
    await animationFrame();
    expect(queryAllTexts(".dropdown-item")).toEqual(["hello"]);
    await contains(".dropdown-item:first").click();
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.defaultValue).toEqual({ operator: "ilike", strings: ["hello"] });
});

test("Create a new text global filter, set a default value ,then restrict values to range", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    setCellContent(model, "B1", "hello");
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await editGlobalFilterDefaultValue("hi");
    await contains(".restrict_to_range input[type=checkbox]").click();
    selectCell(model, "B1");
    await animationFrame();
    await animationFrame(); // SelectionInput component needs an extra tick to update
    await contains(".o-selection-ok").click();
    await contains(".o-autocomplete input").click();
    await animationFrame();
    expect(queryAllTexts(".dropdown-item")).toEqual(["hello"]);
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.defaultValue).toEqual({ operator: "ilike", strings: ["hi"] });
});

test("edit a text global filter with a default value not from the range", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    const sheetId = model.getters.getActiveSheetId();
    addGlobalFilter(model, {
        id: "42",
        type: "text",
        label: "a filter",
        defaultValue: { operator: "ilike", strings: ["Hi"] },
        rangesOfAllowedValues: [toRangeData(sheetId, "B2")],
    });
    setCellContent(model, "B2", "hello"); // the range does not contain the default value
    await animationFrame();
    await openSidePanel(model, env, "42");
    expect(".o_tag").toHaveText("Hi");
    await contains(".o-autocomplete input").click();
    await animationFrame();
    expect(queryAllTexts(".dropdown-item")).toEqual(["hello"]);
    await saveGlobalFilter(); // save without changing anything
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.defaultValue).toEqual({ operator: "ilike", strings: ["Hi"] });
});

test("check range text filter but don't select any range", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await contains(".restrict_to_range input[type=checkbox]").click();
    await animationFrame();
    expect(".o-selection-input input").toHaveValue("");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.rangesOfAllowedValues).toBe(undefined);
});

test("check and uncheck range for text filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "text");
    await editGlobalFilterLabel("My Label");
    await contains(".restrict_to_range input[type=checkbox]").click();
    selectCell(model, "B1");
    await animationFrame();
    await contains(".o-selection-ok").click();
    expect(".o-selection-input input").toHaveValue("B1");
    await contains(".restrict_to_range input[type=checkbox]").click();
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.rangesOfAllowedValues).toBe(undefined);
});

test("Create a new relational global filter", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("product");
    expect(".o_filter_field_offset").toHaveCount(0, {
        message: "No offset for relational filter",
    });
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("Product");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(model.getters.getPivotFieldMatching(pivotId, globalFilter.id)).toEqual({
        chain: "product_id",
        type: "many2one",
    });
});

test("Can select ID in relation filter", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("partner");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(model.getters.getPivotFieldMatching(pivotId, globalFilter.id)).toEqual({
        chain: "id",
        type: "integer",
    });
});

test("Cannot select ID in date filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "date");
    await contains(".o_model_field_selector_value").click();
    expect(target.querySelectorAll("[data-name='id']").length).toBe(0);
});

test("Cannot select ID in text filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "text");
    await contains(".o_model_field_selector_value").click();
    expect(target.querySelectorAll("[data-name='id']").length).toBe(0);
});

test("Create a new many2many relational global filter", async function () {
    defineModels([Vehicle]);
    const serverData = getBasicServerData();
    Partner._fields.vehicle_ids = fields.Many2many({
        relation: "vehicle",
        searchable: true,
        string: "Vehicle",
    });
    serverData.models["ir.model"] = {
        records: [{ id: 34, name: "Vehicle", model: "vehicle" }],
    };
    const { model, pivotId, env } = await createSpreadsheetWithPivot({ serverData });
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("vehicle");
    expect(".o_model_field_selector_value").toHaveText("Vehicle");
    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("Vehicle");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(model.getters.getPivotFieldMatching(pivotId, globalFilter.id)).toEqual({
        chain: "vehicle_ids",
        type: "many2many",
    });
});

test("Panel has collapsible section with field matching in new filters", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "date");
    await animationFrame();
    const collapsible = target.querySelector(".os-collapse");
    expect(".o_spreadsheet_field_matching").toHaveCount(1);
    expect(collapsible).not.toHaveClass("d-none");
});

test("Collapsible section with field matching is collapsed for existing filter", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, THIS_YEAR_GLOBAL_FILTER, {
        pivot: { [pivotId]: { type: "date", chain: "date" } },
    });
    await openSidePanel(model, env, THIS_YEAR_GLOBAL_FILTER.id);
    const collapsible = target.querySelector(".os-collapse");
    expect(collapsible).toHaveClass("d-none");
});

test("Creating a date filter without a data source does not display Field Matching", async function () {
    const { model, env } = await createModelWithDataSource();
    await openSidePanelForCreation(model, env, "date");
    expect(".collapsible_section").toHaveCount(0);
});

test("open relational global filter panel then go to pivot on sheet 2", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    createSheet(model, { sheetId: "sheet2" });
    setCellContent(model, "A1", '=PIVOT.VALUE("1", "probability:avg")', "sheet2");
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("product");
    const fieldMatching = target.querySelector(".o_spreadsheet_field_matching div");
    expect(fieldMatching).toHaveText("Partner Pivot (Pivot #1)", {
        message: "model display name is loaded",
    });
    await saveGlobalFilter();
    model.dispatch("ACTIVATE_SHEET", {
        sheetIdFrom: model.getters.getActiveSheetId(),
        sheetIdTo: "sheet2",
    });
    await animationFrame();
    expect(getCellValue(model, "A1")).toBe(131);
});

test("Prevent selection of a Field Matching before the Related model", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    expect(".o_spreadsheet_field_matching").toHaveCount(0);
    await selectModelForRelation("product");
    expect(".o_spreadsheet_field_matching").toHaveCount(1);
});

test("Display with an existing 'Relation' global filter", async function () {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    const pivotId2 = "PIVOT#2";
    await insertPivotInSpreadsheet(model, pivotId2, { arch: getBasicPivotArch() });
    const label = "MyFoo";
    const filter = {
        id: "42",
        type: "relation",
        modelName: "product",
        label,
    };
    addGlobalFilterWithoutReload(model, filter, {
        pivot: {
            [pivotId]: { type: "many2one", chain: "product_id" }, // first pivotId
            [pivotId2]: { type: "many2one", chain: "product_id" }, // second pivotId
        },
    });
    await openSidePanel(model, env, "42");
    expect(".o_global_filter_label").toHaveValue(label);
    expect(`.o_side_panel_related_model input`).toHaveValue("Product");
    const fieldsMatchingElements = target.querySelectorAll(
        "span.o_model_field_selector_chain_part"
    );
    expect(fieldsMatchingElements.length).toBe(2);
    expect(fieldsMatchingElements[0]).toHaveText("Product");
    expect(fieldsMatchingElements[1]).toHaveText("Product");
});

test("Only related models can be selected", async function () {
    defineModels([Vehicle, Computer]);
    const data = getBasicData();
    data["ir.model"].records = [
        ...IrModel._records,
        {
            id: 36,
            name: "Apple",
            model: "apple",
        },
        {
            id: 34,
            name: "Vehicle",
            model: "vehicle",
        },
        {
            id: 33,
            name: "Computer",
            model: "computer",
        },
    ];
    const vehicle_ids = fields.Many2many({ relation: "vehicle", string: "Vehicle" });
    const computer_ids = fields.One2many({ relation: "computer", string: "Computer" });
    Partner._fields = { ...Partner._fields, vehicle_ids, computer_ids };

    const { model, env } = await createSpreadsheetWithPivot({ serverData: { models: data } });
    await openSidePanelForCreation(model, env, "relation");
    await contains(".o_side_panel_related_model input").click();
    const [model1, model2, model3, model4, model5, model6, model7, model8] =
        target.querySelectorAll(".o-autocomplete--dropdown-item a");
    expect(model1).toHaveText("Apple");
    expect(model2).toHaveText("Computer");
    expect(model3).toHaveText("Currency");
    expect(model4).toHaveText("Partner");
    expect(model5).toHaveText("Product");
    expect(model6).toHaveText("Tag");
    expect(model7).toHaveText("Users");
    expect(model8).toHaveText("Vehicle");
});

test("Fields are ordered by global filter type then relation", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "date");
    await contains(".o_model_field_selector_value").click();
    const [model1, model2, model3, model4, model5, model6, model7] = target.querySelectorAll(
        ".o_model_field_selector_popover_item_name"
    );
    // Date first
    expect(model1).toHaveText("Creation Date");
    expect(model2).toHaveText("Date");
    expect(model3).toHaveText("Last Modified on");
    // Then relation
    expect(model4).toHaveText("Currency");
    expect(model5).toHaveText("Product");
    expect(model6).toHaveText("Tags");
    expect(model7).toHaveText("Users");
});

test("Edit an existing global filter", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    const label = "This year";
    const defaultValue = { operator: "ilike", strings: ["value"] };
    addGlobalFilterWithoutReload(model, { id: "42", type: "text", label, defaultValue });
    await openSidePanel(model, env, "42");
    expect(".o_global_filter_label").toHaveValue(label);
    expect(".o-global-filter-text-value .o_tag").toHaveText("value");
    await editGlobalFilterLabel("New Label");
    await selectFieldMatching("name");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("New Label");
});

test("Trying to duplicate a filter label will trigger a toaster", async function () {
    const uniqueFilterName = "UNIQUE_FILTER";
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "relation",
        label: uniqueFilterName,
        modelName: "product",
    });
    await openSidePanelForCreation(model, env, "text", {
        raiseError: () => {
            expect.step("error");
        },
    });
    await editGlobalFilterLabel(uniqueFilterName);
    await editGlobalFilterDefaultValue("Default Value");
    await selectFieldMatching("name");
    await saveGlobalFilter();
    expect.verifySteps(["error"]);
});

test("Create a new relational global filter with a pivot", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("product");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("Product");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(model.getters.getPivotFieldMatching("PIVOT#1", globalFilter.id)).toEqual({
        chain: "product_id",
        type: "many2one",
    });
});

test("Create a new relational global filter with a chart", async function () {
    const { model, env } = await createSpreadsheetWithChart();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("product");
    await saveGlobalFilter();
    const [chartId] = model.getters.getOdooChartIds();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("Product");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(model.getters.getOdooChartFieldMatching(chartId, globalFilter.id)).toEqual({
        chain: "product_id",
        type: "many2one",
    });
});

test("Create a new relational global filter with a domain", async function () {
    onRpc("/web/domain/validate", () => true);
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("product");
    expect(".o_edit_domain").toHaveCount(0);
    await contains(".o-checkbox:contains(Restrict values with a domain)").click();
    await contains(".o_edit_domain").click();
    await domainHelpers.addNewRule();
    await contains(".modal-footer .btn-primary").click();
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.domainOfAllowedValues).toEqual([["id", "=", 1]]);
});

test("Create a new relational global filter of users will shows the checkbox", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "relation");
    await selectModelForRelation("res.users");
    const defaultUserOption = document.querySelector("[name=user_automatic_filter]");
    expect(defaultUserOption).not.toBe(null);
    expect(defaultUserOption).not.toBeChecked();
    await contains(defaultUserOption).click();
    expect(defaultUserOption).toBeChecked();
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    const id = globalFilter.id;
    const { ids } = model.getters.getGlobalFilterValue(id);
    expect([user.userId]).toEqual(ids);
    expect(globalFilter.defaultValue).toEqual({ operator: "in", ids: "current_user" });
    expect(globalFilter.label).toBe("Users");
});

test("Create a new date filter", async function () {
    mockDate("2022-07-10 00:00:00");
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    insertChartInSpreadsheet(model);
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    await contains(".o-default-value-section input").click();
    await contains(".o-dropdown-item[data-id='this_month']").click();

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    const listFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[1];
    const graphFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[2];

    await selectFieldMatching("date", pivotFieldMatching);
    await selectFieldMatching("date", listFieldMatching);
    await selectFieldMatching("date", graphFieldMatching);

    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.type).toBe("date");
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);
    assertDateDomainEqual("date", "2022-07-01", "2022-07-31", pivotDomain);
    expect(model.getters.getPivotFieldMatching(pivotId, globalFilter.id).offset).toBe(0);
    model.getters.getPivotFieldMatching(pivotId, globalFilter.id);
    const listDomain = model.getters.getListComputedDomain("1");
    assertDateDomainEqual("date", "2022-07-01", "2022-07-31", listDomain);
    expect(model.getters.getListFieldMatching("1", globalFilter.id).offset).toBe(0);
    const chartId = model.getters.getOdooChartIds()[0];
    const graphDomain = model.getters.getChartDataSource(chartId).getComputedDomain();
    assertDateDomainEqual("date", "2022-07-01", "2022-07-31", graphDomain);
    expect(model.getters.getOdooChartFieldMatching(chartId, globalFilter.id).offset).toBe(0);
});

test("Create a new date filter with period offsets", async function () {
    mockDate("2022-07-14 00:00:00");
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    insertChartInSpreadsheet(model);
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    await contains(".o-default-value-section input").click();
    await contains(".o-dropdown-item[data-id='this_month']").click();

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    const listFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[1];
    const chartFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[2];

    // pivot
    await selectFieldMatching("date", pivotFieldMatching);
    await contains(pivotFieldMatching.querySelector("select")).select("-1");
    await contains(pivotFieldMatching.querySelector("input.o_filter_offset_input")).edit("1");

    //list
    await selectFieldMatching("date", listFieldMatching);

    // chart
    await selectFieldMatching("date", chartFieldMatching);
    await contains(chartFieldMatching.querySelector("select")).select("-1");
    await contains(chartFieldMatching.querySelector("input.o_filter_offset_input")).edit("2");

    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.type).toBe("date");
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);

    expect(model.getters.getPivotFieldMatching(pivotId, globalFilter.id).offset).toBe(-1);
    assertDateDomainEqual("date", "2022-06-01", "2022-06-30", pivotDomain);
    const listDomain = model.getters.getListComputedDomain("1");
    expect(model.getters.getListFieldMatching("1", globalFilter.id).offset).toBe(0);
    assertDateDomainEqual("date", "2022-07-01", "2022-07-31", listDomain);
    const chartId = model.getters.getOdooChartIds()[0];
    const chartDomain = model.getters.getChartDataSource(chartId).getComputedDomain();
    expect(model.getters.getOdooChartFieldMatching(chartId, globalFilter.id).offset).toBe(-2);
    assertDateDomainEqual("date", "2022-05-01", "2022-05-31", chartDomain);
});

test("Cannot create a new date filter with period offsets without setting the field chain first", async () => {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    expect(".o_filter_field_offset select.o-input").toHaveCount(0);

    // pivot
    await selectFieldMatching("date", pivotFieldMatching);
    expect(".o_filter_field_offset select.o-input").toHaveCount(1);
    expect(".o_filter_field_offset select.o-input").toHaveProperty("disabled", false);
});

test("Creating a new date filter with large period offsets defaults to 50", async () => {
    mockDate("2022-07-14 00:00:00");
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    await contains(".o-default-value-section input").click();
    await contains(".o-dropdown-item[data-id='last_30_days']").click();

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    await selectFieldMatching("date", pivotFieldMatching);
    await contains(pivotFieldMatching.querySelector("select")).select("-1");
    await contains(pivotFieldMatching.querySelector("input.o_filter_offset_input")).edit("9999");
    await saveGlobalFilter();
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);
    assertDateDomainEqual("date", "2018-05-07", "2018-06-05", pivotDomain);
});

test("Create a new relative date filter with an empty default value", async () => {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    insertChartInSpreadsheet(model);
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    const listFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[1];
    const graphFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[2];

    await selectFieldMatching("date", pivotFieldMatching);
    await selectFieldMatching("date", listFieldMatching);
    await selectFieldMatching("date", graphFieldMatching);

    await contains(graphFieldMatching.querySelector("select")).select("-1");
    await contains(graphFieldMatching.querySelector("input.o_filter_offset_input")).edit("2");

    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(globalFilter.type).toBe("date");
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);
    expect(pivotDomain).toEqual([]);
    const listDomain = model.getters.getListComputedDomain("1");
    expect(listDomain).toEqual([]);
    const chartId = model.getters.getOdooChartIds()[0];
    const chartDomain = model.getters.getChartDataSource(chartId).getComputedDomain();
    expect(chartDomain).toEqual([]);
});

test("Create a new relative date filter", async function () {
    mockDate("2022-07-14 00:00:00");
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    insertChartInSpreadsheet(model);
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    await contains(".o-default-value-section input").click();
    await contains(".o-dropdown-item[data-id='last_30_days']").click();

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    const listFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[1];
    const graphFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[2];

    await selectFieldMatching("date", pivotFieldMatching);
    await contains(pivotFieldMatching.querySelector("select")).select("-1");
    await contains(pivotFieldMatching.querySelector("input.o_filter_offset_input")).edit("7");

    await selectFieldMatching("date", listFieldMatching);
    await contains(listFieldMatching.querySelector("select")).select("1");
    await contains(listFieldMatching.querySelector("input.o_filter_offset_input")).edit("2");

    await selectFieldMatching("date", graphFieldMatching);
    await contains(graphFieldMatching.querySelector("select")).select("-1");
    await contains(graphFieldMatching.querySelector("input.o_filter_offset_input")).edit("3");

    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.defaultValue).toBe("last_30_days");
    expect(globalFilter.type).toBe("date");
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);
    assertDateDomainEqual("date", "2021-11-17", "2021-12-16", pivotDomain);
    const listDomain = model.getters.getListComputedDomain("1");
    assertDateDomainEqual("date", "2022-08-14", "2022-09-12", listDomain);
    const chartId = model.getters.getOdooChartIds()[0];
    const chartDomain = model.getters.getChartDataSource(chartId).getComputedDomain();
    assertDateDomainEqual("date", "2022-03-17", "2022-04-15", chartDomain);
});

test("Create a new relative date filter with a negative offset should save the absolute value", async function () {
    mockDate("2022-07-14 00:00:00");
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    insertChartInSpreadsheet(model);
    await openSidePanelForCreation(model, env, "date");
    await editGlobalFilterLabel("My Label");

    await contains(".o-default-value-section input").click();
    await contains(".o-dropdown-item[data-id='last_30_days']").click();

    const pivotFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[0];
    const listFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[1];
    const graphFieldMatching = target.querySelectorAll(".o_spreadsheet_field_matching")[2];

    await selectFieldMatching("date", pivotFieldMatching);
    await contains(pivotFieldMatching.querySelector("select")).select("-1");
    await contains(pivotFieldMatching.querySelector("input.o_filter_offset_input")).edit("-7", {
        instantly: true,
    });

    await selectFieldMatching("date", listFieldMatching);
    await contains(listFieldMatching.querySelector("select")).select("1");
    await contains(listFieldMatching.querySelector("input.o_filter_offset_input")).edit("-2", {
        instantly: true,
    });

    await selectFieldMatching("date", graphFieldMatching);
    await contains(graphFieldMatching.querySelector("select")).select("-1");
    await contains(graphFieldMatching.querySelector("input.o_filter_offset_input")).edit("-2", {
        instantly: true,
    });

    await saveGlobalFilter();

    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.defaultValue).toBe("last_30_days");
    expect(globalFilter.type).toBe("date");
    const pivotDomain = model.getters.getPivotComputedDomain(pivotId);
    assertDateDomainEqual("date", "2021-11-17", "2021-12-16", pivotDomain);
    const listDomain = model.getters.getListComputedDomain("1");
    assertDateDomainEqual("date", "2022-08-14", "2022-09-12", listDomain);
    const chartId = model.getters.getOdooChartIds()[0];
    const chartDomain = model.getters.getChartDataSource(chartId).getComputedDomain();
    assertDateDomainEqual("date", "2022-04-16", "2022-05-15", chartDomain);
});

test("Change all domains -> Set corresponding model should allow saving", async function () {
    const serverData = getBasicServerData();
    defineModels([Vehicle]);
    Partner._fields.vehicle_ids = fields.Many2many({ relation: "vehicle", string: "Vehicle" });
    serverData.models["ir.model"].records = [
        ...IrModel._records,
        {
            id: 34,
            name: "Vehicle",
            model: "vehicle",
        },
    ];

    const { model, env } = await createSpreadsheetWithPivot({ serverData });
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "relation",
        modelName: "product",
        label: "Product",
    });
    await openSidePanel(model, env, "42");

    expect(".o_global_filter_label").toHaveValue("Product");

    // visible: false to skip the collapsible. We really don't want to use the collapsible here, as bootstrap dispatches
    // scroll events which have the side effect to close the autocomplete
    await contains(".o_model_field_selector_value", { visible: false }).click();
    await contains(target.querySelectorAll(".o_model_field_selector_popover_item")[3]).click();
    await contains(".o_model_field_selector_popover_close").click();
    await selectModelForRelation("vehicle");

    await editGlobalFilterLabel("test case");
    await saveGlobalFilter();
    expect(model.getters.getGlobalFilters()[0].label).toBe("test case");
});

test("Filter edit side panel is initialized with the correct values", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    addGlobalFilterWithoutReload(
        model,
        {
            id: "42",
            type: "date",
            label: "This month",
            defaultValue: "this_month",
        },
        {
            pivot: {
                [pivotId]: { chain: "date", type: "date", offset: 0 },
            },
            list: {
                1: { chain: "date", type: "date", offset: 1 },
            },
        }
    );
    await openSidePanel(model, env, "42");

    expect(".o_global_filter_label").toHaveValue("This month");

    const pivotField = ".o_spreadsheet_field_matching:eq(0)";
    const pivotFieldValue = `${pivotField} .o_model_field_selector_value span`;
    expect(pivotFieldValue).toHaveText("Date");
    expect(`${pivotField} select`).toHaveValue("0");

    const listField = ".o_spreadsheet_field_matching:eq(1)";
    const listFieldValue = `${listField} .o_model_field_selector_value span`;
    expect(listFieldValue).toHaveText("Date");
    expect(`${listField} select`).toHaveValue("1");
});

test("Empty field is marked as warning", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "text",
        label: "Text Filter",
    });
    await openSidePanel(model, env, "42");
    expect(target.querySelector(".o_spreadsheet_field_matching")).toHaveClass("o_missing_field");
});

test("Can save with an empty field", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "text",
        label: "Text Filter",
    });
    await openSidePanel(model, env, "42");
    await saveGlobalFilter();
    expect(model.getters.getPivotFieldMatching(pivotId, "42")).toBe(undefined);
});

test("Field matching edition is saved even without others modifications", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(
        model,
        {
            id: "42",
            type: "text",
            label: "Text Filter",
        },
        {
            pivot: {
                [pivotId]: { chain: "name", type: "char" },
            },
        }
    );
    await openSidePanel(model, env, "42");
    await contains(".collapsor").click();
    await contains(".o_model_field_selector_controls .fa-times").click();
    await saveGlobalFilter();
    expect(model.getters.getPivotFieldMatching(pivotId, "42")).toEqual({});
});

test("Can clear a field matching an invalid field", async function () {
    const { model, pivotId, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(
        model,
        {
            id: "42",
            type: "text",
            label: "Text Filter",
            name: "test",
        },
        {
            pivot: {
                [pivotId]: { chain: "not_a_field", type: "" },
            },
        }
    );
    await openSidePanel(model, env, "42");
    await contains(".collapsor").click(); // uncollapse the field matching
    expect(".o_model_field_selector_warning").toHaveCount(1);
    expect(".o_spreadsheet_field_matching .o_model_field_selector").toHaveText("not_a_field");
    await contains(".o_model_field_selector .fa.fa-times").click();
    expect(".o_spreadsheet_field_matching .o_model_field_selector").toHaveText("");
});

test("Create a new relational global filter with a list snapshot", async function () {
    const spreadsheetData = {
        lists: {
            1: {
                id: 1,
                columns: ["foo", "contact_name"],
                domain: [],
                model: "partner",
                orderBy: [],
                context: {},
                fieldMatching: {},
            },
        },
    };
    const { model, env } = await createModelWithDataSource({ spreadsheetData });
    await openSidePanelForCreation(model, env, "relation");
    await contains('.o_side_panel_related_model input[type="text"]').click();
    await contains(`.o_model_selector_product`).click();
    await contains(".o_global_filter_save").click();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("Product");
    expect(globalFilter.defaultValue).toBe(undefined);
    expect(model.getters.getListFieldMatching("1", globalFilter.id)).toEqual({
        chain: "product_id",
        type: "many2one",
    });
});

test("Cannot save filter with empty label", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    addGlobalFilterWithoutReload(model, {
        id: "42",
        type: "text",
        label: "Text Filter",
    });
    await openSidePanel(model, env, "42", {
        notifyUser: (notif) => {
            expect.step("notifyUser");
            expect(notif.type).toBe("danger");
            expect(notif.text).toBe("Label is missing.");
            expect(notif.sticky).toBe(false);
        },
    });
    await contains(".o_global_filter_label").edit("");
    await contains(".o_global_filter_save").click();
    expect.verifySteps(["notifyUser"]);
});

test("Create a new numeric global filter with empty value", async function () {
    const { model, env } = await createSpreadsheetWithPivot();
    await openSidePanelForCreation(model, env, "numeric");
    await editGlobalFilterLabel("My Label");
    await contains(".o-global-filter-numeric-value").edit("");
    await saveGlobalFilter();
    const [globalFilter] = model.getters.getGlobalFilters();
    expect(globalFilter.label).toBe("My Label");
    expect(globalFilter.type).toBe("numeric");
    expect(globalFilter.defaultValue).toBe(undefined);
});

test("Cannot create a filter if a datasource is in error", async function () {
    const { model, env } = await createSpreadsheetWithList({
        mockRPC: async function (route, { model, method, kwargs }) {
            if (model === "partner" && method === "fields_get") {
                throw makeServerError({ code: 404 });
            }
        },
    });

    const comp = await openSidePanelForCreation(model, env, "text");
    expect(".o-validation-error").toHaveCount(1);
    expect(".o_global_filter_cancel").toHaveCount(1);
    expect(".o_global_filter_save").toHaveCount(0);

    for (const type of Object.keys(SIDE_PANELS)) {
        comp.props.type = type;
        await animationFrame();
        expect(".o-validation-error").toHaveCount(1);
        expect(".o_global_filter_cancel").toHaveCount(1);
        expect(".o_global_filter_save").toHaveCount(0);
    }
});

test("Default value and subdomain are hidden for invalid relational filters", async () => {
    const { model, env } = await createSpreadsheetWithList({
        mockRPC: async function (route, { model, method, kwargs }) {
            if (model === "unknown" && method === "fields_get") {
                throw makeServerError({ code: 404 });
            }
        },
    });

    addGlobalFilterWithoutReload(model, {
        id: "43",
        type: "relation",
        label: "Relational Filter",
        modelName: "unknown",
    });

    await openSidePanel(model, env, "43");
    expect(".o_multi_record_selector").toHaveCount(0);
});
