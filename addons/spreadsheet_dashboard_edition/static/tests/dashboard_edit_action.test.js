import { describe, expect, test } from "@odoo/hoot";
import { queryText } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { registries } from "@odoo/o-spreadsheet";
import { getCellContent } from "@spreadsheet/../tests/helpers/getters";
import { doMenuAction } from "@spreadsheet/../tests/helpers/ui";
import { contains, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { Deferred } from "@web/core/utils/concurrency";
import { actionService } from "@web/webclient/actions/action_service";
import {
    defineSpreadsheetDashboardEditionModels,
    getDashboardBasicServerData,
} from "./helpers/test_data";
import { createDashboardEditAction, createNewDashboard } from "./helpers/test_helpers";

defineSpreadsheetDashboardEditionModels();

describe.current.tags("desktop");

const { topbarMenuRegistry } = registries;

test("open dashboard with existing data", async function () {
    const serverData = getDashboardBasicServerData();
    const spreadsheetId = createNewDashboard(serverData, {
        sheets: [
            {
                cells: {
                    A1: "Hello",
                },
            },
        ],
    });
    const { model } = await createDashboardEditAction({ serverData, spreadsheetId });
    expect(getCellContent(model, "A1")).toBe("Hello");
});

test("copy dashboard from topbar menu", async function () {
    const serviceRegistry = registry.category("services");
    serviceRegistry.add("actionMain", actionService);
    const fakeActionService = {
        dependencies: ["actionMain"],
        start(env, { actionMain }) {
            return {
                ...actionMain,
                doAction: (actionRequest, options = {}) => {
                    if (
                        actionRequest.tag === "action_edit_dashboard" &&
                        actionRequest.params.spreadsheet_id === 111
                    ) {
                        expect.step("redirect");
                    } else {
                        return actionMain.doAction(actionRequest, options);
                    }
                },
            };
        },
    };
    serviceRegistry.add("action", fakeActionService, { force: true });
    onRpc("spreadsheet.dashboard", "copy", ({ kwargs }) => {
        expect.step("dashboard_copied");
        const { spreadsheet_data, thumbnail } = kwargs.default;
        expect(spreadsheet_data).not.toBe(undefined);
        expect(thumbnail).toBe(undefined);
        return [111];
    });
    const { env } = await createDashboardEditAction();
    await doMenuAction(topbarMenuRegistry, ["file", "make_copy"], env);
    expect.verifySteps(["dashboard_copied", "redirect"]);
});

test("share dashboard from control panel", async function () {
    const serverData = getDashboardBasicServerData();
    const spreadsheetId = createNewDashboard(serverData, {
        sheets: [
            {
                cells: {
                    A1: "Hello",
                },
            },
        ],
    });
    patchWithCleanup(browser.navigator.clipboard, {
        writeText: async (url) => {
            expect.step("share url copied");
            expect(url).toBe("localhost:8069/share/url/132465");
        },
    });
    onRpc("spreadsheet.dashboard.share", "action_get_share_url", async ({ args }) => {
        await def;
        expect.step("dashboard_shared");
        const [shareVals] = args;
        const excel = JSON.parse(JSON.stringify(model.exportXLSX().files));
        expect(shareVals).toEqual({
            spreadsheet_data: JSON.stringify(model.exportData()),
            dashboard_id: spreadsheetId,
            excel_files: excel,
        });
        return "localhost:8069/share/url/132465";
    });
    const def = new Deferred();
    const { model } = await createDashboardEditAction({
        serverData,
        spreadsheetId,
    });
    expect(".spreadsheet_share_dropdown").toHaveCount(0);
    await contains("i.fa-share-alt").click();
    expect(".spreadsheet_share_dropdown .o_loading_state").toHaveText("Generating sharing link");
    def.resolve();
    await animationFrame();
    expect(".spreadsheet_share_dropdown .o_loading_state").toHaveCount(0);
    expect.verifySteps(["dashboard_shared", "share url copied"]);
    expect(".o_field_CopyClipboardChar").toHaveText("localhost:8069/share/url/132465");
    await contains(".fa-clipboard").click();
    expect.verifySteps(["share url copied"]);
});

test("publish dashboard from control panel", async function () {
    onRpc("spreadsheet.dashboard", "write", ({ args }) => {
        expect.step("dashboard_published");
        expect(args[1]).toEqual({ is_published: true });
    });
    await createDashboardEditAction();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Unpublished");
    expect(".o_sp_publish_dashboard .o-checkbox input").not.toBeChecked();
    await contains(".o_sp_publish_dashboard .o-checkbox input").click();
    expect(".o_sp_publish_dashboard .o-checkbox input").toBeChecked();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Published");
    expect.verifySteps(["dashboard_published"]);
});

test("unpublish dashboard from control panel", async function () {
    onRpc("/spreadsheet/data/spreadsheet.dashboard/*", () => ({
        data: {},
        revisions: [],
        name: "Dashboard",
        isReadonly: false,
        is_published: true,
    }));
    onRpc("spreadsheet.dashboard", "write", ({ args }) => {
        expect.step("dashboard_unpublished");
        expect(args[1]).toEqual({ is_published: false });
    });
    await createDashboardEditAction();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Published");
    expect(".o_sp_publish_dashboard .o-checkbox input").toBeChecked();
    await contains(".o_sp_publish_dashboard .o-checkbox input").click();
    expect(".o_sp_publish_dashboard .o-checkbox input").not.toBeChecked();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Unpublished");
    expect.verifySteps(["dashboard_unpublished"]);
});

test("toggles publish state when clicking on checkbox label", async function () {
    onRpc("spreadsheet.dashboard", "write", ({ args }) => {
        expect.step("dashboard_published");
        expect(args[1]).toEqual({ is_published: true });
    });
    await createDashboardEditAction();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Unpublished");
    expect(".o_sp_publish_dashboard .o-checkbox input").not.toBeChecked();
    await contains(".o_sp_publish_dashboard .o-checkbox .form-check-label").click();
    expect(".o_sp_publish_dashboard .o-checkbox input").toBeChecked();
    expect(queryText(".o_sp_publish_dashboard")).toInclude("Published");
    expect.verifySteps(["dashboard_published"]);
});
