import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { createSpreadsheetDashboard } from "@spreadsheet_dashboard/../tests/helpers/dashboard_action";
import { mockService, onRpc, serverState } from "@web/../tests/web_test_helpers";
import { defineSpreadsheetDashboardEditionModels } from "./helpers/test_data";

describe.current.tags("desktop");
defineSpreadsheetDashboardEditionModels();

test("Clicking 'Edit' icon navigates to dashboard edit view", async function () {
    serverState.debug = "1";

    onRpc("spreadsheet.dashboard", "action_edit_dashboard", ({ method }) => {
        expect.step(method);
        return {
            type: "ir.actions.client",
            tag: "action_edit_dashboard",
            params: {
                spreadsheet_id: 1,
            },
        };
    });

    await createSpreadsheetDashboard();
    mockService("action", {
        doAction(action) {
            expect.step("doAction");
            expect(action.params.spreadsheet_id).toBe(1);
            expect(action.tag).toBe("action_edit_dashboard");
        },
    });
    await click(".o_edit_dashboard");
    await animationFrame();
    expect.verifySteps(["action_edit_dashboard", "doAction"]);
});

test("User without edit permissions does not see the 'Edit' option on the dashboard (Debug mode ON)", async function () {
    serverState.debug = "1";
    onRpc("has_group", () => false);
    await createSpreadsheetDashboard();
    expect(".o_edit_dashboard").toHaveCount(0);
});

test("User with edit permissions sees the 'Edit' option on the dashboard (Debug mode ON)", async function () {
    serverState.debug = "1";
    onRpc("has_group", () => true);
    await createSpreadsheetDashboard();
    expect(".o_search_panel_category_value .o_edit_dashboard").toHaveCount();
});

test("User with edit permissions does not see the 'Edit' option on the dashboard (Debug mode OFF)", async function () {
    onRpc("has_group", () => true);
    await createSpreadsheetDashboard();
    expect(".o_edit_dashboard").toHaveCount(0);
});

test("Can edit a non-active dashboard", async function () {
    serverState.debug = "1";

    onRpc("spreadsheet.dashboard", "action_edit_dashboard", ({ args, method }) => {
        expect.step(method);
        return {
            type: "ir.actions.client",
            tag: "action_edit_dashboard",
            params: {
                spreadsheet_id: args[0],
            },
        };
    });

    await createSpreadsheetDashboard();
    mockService("action", {
        doAction(action) {
            expect.step("doAction");
            expect(action.params.spreadsheet_id).toBe(2);
            expect(action.tag).toBe("action_edit_dashboard");
        },
    });
    await click(".o_edit_dashboard:eq(1)");
    await animationFrame();
    expect.verifySteps(["action_edit_dashboard", "doAction"]);
});

test("tooltip for editing standard dashboards", async function () {
    serverState.debug = "1";

    onRpc("spreadsheet.dashboard.group", "web_search_read", ({ kwargs, method }) => {
        expect(kwargs.specification.published_dashboard_ids.fields.is_from_data).toEqual({});
        return {
            length: 1,
            records: [
                {
                    id: 8,
                    name: "CRM",
                    published_dashboard_ids: [
                        {
                            id: 1,
                            name: "My custom dashboard",
                            is_favorite: false,
                            is_from_data: false,
                        },
                        {
                            id: 2,
                            name: "Leads",
                            is_favorite: false,
                            is_from_data: true,
                        },
                    ],
                },
            ],
        };
    });
    await createSpreadsheetDashboard();
    expect(".o_edit_dashboard:eq(0)").not.toHaveClass("btn-warning", { exact: false });
    expect(".o_edit_dashboard:eq(1)").toHaveClass("btn-warning", { exact: false });
});
