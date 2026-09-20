import { describe, expect, test } from "@odoo/hoot";

import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";
import { stores } from "@odoo/o-spreadsheet";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { RelatedFilters } from "@spreadsheet_edition/bundle/global_filters/components/related_filters/related_filters";
import { addGlobalFilter } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import {
    createSpreadsheetWithList,
    insertListInSpreadsheet,
} from "@spreadsheet/../tests/helpers/list";
const { useStoreProvider, ModelStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

class Parent extends Component {
    static template = xml`<RelatedFilters t-props="props"/>`;
    static components = { RelatedFilters };
    static props = {
        resModel: String,
        dataSourceId: String,
        dataSourceType: String,
    };

    setup() {
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.env.model);

        onMounted(() => {
            this.env.model.on("update", this, () => this.render(true));
            stores.on("store-updated", this, this.render.bind(this, true));
        });
        onWillUnmount(() => {
            this.env.model.off("update", this);
            stores.off("store-updated", this);
        });
    }
}

async function openSidePanel(model, env, props) {
    await mountWithCleanup(Parent, { env, props });
}

test("can link a new field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(model, { id: "43", type: "text", label: "Filter" });
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".pivot-dimension").toHaveClass("opacity-50");
    expect(".o_model_field_selector").toHaveCount(0);
    await contains(".o-button-icon.fa-unlink").click();
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:first").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "display_name",
        type: "char",
    });
});

test("can unlink a field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "text", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "display_name",
                    type: "char",
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("Display name");
    await contains(".o-button-icon.fa-link").click();
    expect(".pivot-dimension").toHaveClass("opacity-50");
    expect(".o_model_field_selector").toHaveCount(0);
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({});
});

test("can update a field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "text", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "name",
                    type: "char",
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("name");
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:contains(Display name)").click();
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "display_name",
        type: "char",
    });
});

test("cannot save a wrong field", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(model, { id: "43", type: "text", label: "Filter" });
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    await contains(".o-button-icon.fa-unlink").click();
    await contains(".o_model_field_selector").click();
    // Currency is not a text field
    await contains(".o_model_field_selector_popover_item_name:contains(Currency)").click();
    expect(".pivot-dimension-invalid").toHaveCount(1);
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toBe(undefined);
});

test("can change date filter offset", async () => {
    const { model, env, pivotId } = await createSpreadsheetWithPivot();
    await addGlobalFilter(
        model,
        { id: "43", type: "date", label: "Filter" },
        {
            pivot: {
                [pivotId]: {
                    chain: "date",
                    type: "date",
                    offset: 0,
                },
            },
        }
    );
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: pivotId,
        dataSourceType: "pivot",
    });
    expect(".o_model_field_selector").toHaveText("Date");
    expect(".o_filter_field_offset select").toHaveValue("0");
    await contains(".o_filter_field_offset select").select("1"); // Next
    await contains(".o_filter_offset_input").edit("4");
    expect(model.getters.getPivotFieldMatching(pivotId, "43")).toEqual({
        chain: "date",
        type: "date",
        offset: 4,
    });
});

test("can change list field matching with non-set filter", async () => {
    const { model, env } = await createSpreadsheetWithList();
    await addGlobalFilter(model, {
        id: "42",
        type: "relation",
        label: "Filter",
        modelName: "partner",
    });
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "product_id"],
    });
    const [list1, list2] = model.getters.getListIds();
    expect(model.getters.getListFieldMatching(list1, "42")).toBe(undefined);
    expect(model.getters.getListFieldMatching(list2, "42")).toBe(undefined);
    await openSidePanel(model, env, {
        resModel: "partner",
        dataSourceId: list1,
        dataSourceType: "list",
    });
    await contains(".fa-unlink").click();
    await contains(".o_model_field_selector").click();
    await contains(".o_model_field_selector_popover_item_name:contains(Id)").click();
    expect(model.getters.getListFieldMatching(list1, "42")).toEqual({
        chain: "id",
        type: "integer",
    });
    expect(model.getters.getListFieldMatching(list2, "42")).toEqual({});
});
