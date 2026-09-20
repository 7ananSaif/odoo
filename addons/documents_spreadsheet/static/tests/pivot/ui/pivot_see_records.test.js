import {
    defineDocumentSpreadsheetModels,
    DocumentsDocument,
    getBasicData,
    getBasicServerData,
} from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheetFromPivotView } from "@documents_spreadsheet/../tests/helpers/pivot_helpers";
import { expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { selectCell } from "@spreadsheet/../tests/helpers/commands";
import { contains, mockService } from "@web/../tests/web_test_helpers";
const { Model } = spreadsheet;
const { cellMenuRegistry } = spreadsheet.registries;

defineDocumentSpreadsheetModels();

test("Can see records and go back after a pivot insertion", async function () {
    const m = new Model();
    const models = getBasicData();
    models["documents.document"].records = [
        {
            spreadsheet_data: JSON.stringify(m.exportData()),
            name: "a spreadsheet",
            folder_id: false,
            handler: "spreadsheet",
            id: 456,
            is_favorited: false,
        },
    ];
    const serverData = {
        models: models,
        views: getBasicServerData().views,
    };
    const { model, env } = await createSpreadsheetFromPivotView({
        documentId: 456,
        serverData,
    });
    // Go the the list view and go back, a third pivot should not be opened
    selectCell(model, "B3");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "pivot_see_records");
    await root.execute(env);
    await animationFrame();
    expect(".o-spreadsheet").toHaveCount(0);
    await contains(document.body.querySelector(".o_back_button")).click();
    await animationFrame();
    expect(".o-spreadsheet").toHaveCount(1);
});

test("Middle-click on 'See records' opens the records in a new tab", async function () {
    const models = getBasicData();
    models["documents.document"].records = [
        DocumentsDocument._records[0],
        {
            spreadsheet_data: JSON.stringify(new Model().exportData()),
            name: "a spreadsheet",
            folder_id: 1,
            handler: "spreadsheet",
            id: 456,
            is_favorited: false,
        },
    ];
    const serverData = {
        models,
        views: getBasicServerData().views,
    };

    const { model, env } = await createSpreadsheetFromPivotView({
        documentId: 456,
        serverData,
    });

    mockService("action", {
        doAction(_, options) {
            expect.step("doAction");
            expect(options).toEqual({
                newWindow: true,
                viewType: "list",
            });
            return Promise.resolve(true);
        },
    });

    selectCell(model, "B3");
    const action = cellMenuRegistry.getAll().find((item) => item.id === "pivot_see_records");
    await action.execute(env, true);
    expect.verifySteps(["doAction"]);
});
