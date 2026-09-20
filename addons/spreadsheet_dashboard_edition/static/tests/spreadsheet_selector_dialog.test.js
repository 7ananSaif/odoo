import { describe, expect, test } from "@odoo/hoot";
import { contains, mountWithCleanup, mockService, onRpc } from "@web/../tests/web_test_helpers";
import { makeSpreadsheetMockEnv } from "@spreadsheet/../tests/helpers/model";
import { SpreadsheetSelectorDialog } from "@spreadsheet_edition/assets/components/spreadsheet_selector_dialog/spreadsheet_selector_dialog";
import { defineSpreadsheetDashboardEditionModels } from "@spreadsheet_dashboard_edition/../tests/helpers/test_data";

describe.current.tags("desktop");
defineSpreadsheetDashboardEditionModels();

function getDefaultProps() {
    return {
        type: "PIVOT",
        name: "Pipeline",
        actionOptions: {},
        close: () => {},
    };
}

async function mountSpreadsheetSelectorDialog(config = {}) {
    const env = await makeSpreadsheetMockEnv({
        mockRPC: config.mockRPC,
    });
    // @ts-ignore
    env.dialogData = { isActive: true, close: () => {} };
    const props = { ...getDefaultProps(), ...(config.props || {}) };
    await mountWithCleanup(SpreadsheetSelectorDialog, { env, props });
    return { env };
}

onRpc("spreadsheet.mixin", "get_selector_spreadsheet_models", () => [
    { model: "spreadsheet.dashboard", display_name: "Dashboards", allow_create: true },
]);

test("Allows inserting list/pivot/graph view into a new blank dashboard", async () => {
    mockService("action", {
        doAction(action) {
            expect.step("doAction");
            expect(action.params.spreadsheet_id).toBe(789);
        },
    });

    await mountSpreadsheetSelectorDialog({
        mockRPC: async (_, args) => {
            if (
                args.model === "spreadsheet.dashboard" &&
                args.method === "action_open_spreadsheet"
            ) {
                expect.step("action_open_spreadsheet");
                return {
                    type: "ir.actions.client",
                    tag: "action_open_spreadsheet",
                    params: { spreadsheet_id: 789 },
                };
            }
        },
    });

    await contains(".o-blank-spreadsheet-grid img").click();
    await contains(".modal-content .modal-footer .btn-primary").click();
    await contains(".modal-content .modal-footer .o_form_button_save").click();

    expect.verifySteps(["action_open_spreadsheet", "doAction"]);
});

test("re-enables Insert button after cancelling dashboard creation form view", async () => {
    await mountSpreadsheetSelectorDialog();

    await contains(".o-blank-spreadsheet-grid img").click();
    await contains(".modal-content .modal-footer .btn-primary").click();
    await contains(".modal-content .modal-footer .o_form_button_cancel").click();

    expect(".modal-content .modal-footer .btn-primary").toHaveCount(1);
    expect(".modal-content .modal-footer .btn-primary").not.toHaveAttribute("disabled");
});
