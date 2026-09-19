import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { describe, expect, test } from "@odoo/hoot";
import { stores } from "@odoo/o-spreadsheet";
import { createSpreadsheetWithPivot } from "@spreadsheet/../tests/helpers/pivot";
import { contains, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";
import { NewPivotSidePanel } from "@spreadsheet_edition/bundle/pivot/side_panels/new_pivot_side_panel/new_pivot_side_panel";
const { useStoreProvider, ModelStore } = stores;

defineSpreadsheetModels();
describe.current.tags("desktop");

class Parent extends Component {
    static template = xml/* xml */ `
        <NewPivotSidePanel onCloseSidePanel="() => {}"/>
    `;
    static components = { NewPivotSidePanel };
    static props = {
        model: Object,
    };

    setup() {
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.props.model);

        onMounted(() => {
            this.props.model.on("update", this, () => this.render(true));
            stores.on("store-updated", this, this.render.bind(this, true));
        });
        onWillUnmount(() => {
            this.props.model.off("update", this);
            stores.off("store-updated", this);
        });
    }
}

async function openSidePanel(model, env) {
    env.notifyUser = env.notifyUser || (() => {});
    env.openSidePanel = env.openSidePanel || (() => {});
    await mountWithCleanup(Parent, { env, props: { model } });
}

test("Open new pivot side panel", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".o_new_pivot_side_panel").toHaveCount(1);
});

test("Cannot save without model", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    expect(".primary").toHaveAttribute("disabled");
});

test("Save button is enabled when a model is selected", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    expect(".primary").not.toHaveAttribute("disabled");
});

test("Create a new pivot", async function () {
    const { env, model } = await createSpreadsheetWithPivot();
    const sheetId = model.getters.getActiveSheetId();
    expect(model.getters.getPivotIds()).toHaveLength(1);
    await openSidePanel(model, env);
    await contains(".o_model_selector input").click();
    await contains(".o_model_selector_partner").click();
    await contains(".o_new_pivot_side_panel .primary").click();
    expect(model.getters.getPivotIds()).toHaveLength(2);
    expect(model.getters.getActiveSheetId()).not.toBe(sheetId);
});
