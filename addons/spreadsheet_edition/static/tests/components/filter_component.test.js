import { describe, expect, test } from "@odoo/hoot";
import { makeMockEnv, mountWithCleanup, contains } from "@web/../tests/web_test_helpers";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { FilterComponent } from "@spreadsheet_edition/bundle/global_filters/filter_component";
import { addGlobalFilterWithoutReload } from "@spreadsheet/../tests/helpers/commands";
import { Model } from "@odoo/o-spreadsheet";

describe.current.tags("desktop");
defineSpreadsheetModels();

/**
 *
 * @param env
 */
async function mountFilterComponent(env) {
    await mountWithCleanup(FilterComponent, { env });
}

test("Filter component is rendered without the badge if there is no active filters", async function () {
    const model = new Model();
    const env = await makeMockEnv({ model });
    addGlobalFilterWithoutReload(model, {
        id: "1",
        type: "text",
        label: "My filter",
    });
    await mountFilterComponent(env);
    expect(".o_topbar_filter_icon").toHaveCount(1);
    expect(".o_topbar_filter_icon .badge").toHaveCount(0);
});

test("Filter component is rendered with the badge if there is an active filter", async function () {
    const model = new Model();
    const env = await makeMockEnv({ model });
    addGlobalFilterWithoutReload(model, {
        id: "1",
        type: "text",
        label: "My filter",
        defaultValue: { operator: "ilike", strings: ["foo"] },
    });
    await mountFilterComponent(env);
    expect(".o_topbar_filter_icon").toHaveCount(1);
    expect(".o_topbar_filter_icon .badge").toHaveCount(1);
});

test("Badge displays the number of active filters", async function () {
    const model = new Model();
    const env = await makeMockEnv({ model });
    addGlobalFilterWithoutReload(model, {
        id: "1",
        type: "text",
        label: "My filter",
        defaultValue: { operator: "ilike", strings: ["foo"] },
    });
    addGlobalFilterWithoutReload(model, {
        id: "2",
        type: "text",
        label: "Another filter",
    });
    await mountFilterComponent(env);
    expect(".o_topbar_filter_icon").toHaveCount(1);
    expect(".o_topbar_filter_icon .badge").toHaveCount(1);
    expect(".o_topbar_filter_icon .badge").toHaveText("1");
});

test("Clicking on the filter button opens the dialog if there are configured filters", async function () {
    const model = new Model();
    const env = await makeMockEnv({ model });
    addGlobalFilterWithoutReload(model, {
        id: "1",
        type: "text",
        label: "My filter",
    });
    await mountFilterComponent(env);
    expect(".o_topbar_filter_icon").toHaveCount(1);
    await contains(".o_topbar_filter_icon").click();
    expect(".o_dialog").toHaveCount(1);
});

test("Clicking on the filter button opens the side panel if there are no configured filters", async function () {
    const model = new Model();
    const env = await makeMockEnv({ model });
    env.toggleSidePanel = () => {
        expect.step("toggleSidePanel");
    };
    await mountFilterComponent(env);
    expect.verifySteps([]);
    expect(".o_topbar_filter_icon").toHaveCount(1);
    await contains(".o_topbar_filter_icon").click();
    expect.verifySteps(["toggleSidePanel"]);
});
