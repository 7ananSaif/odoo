import {
    defineDocumentSpreadsheetModels,
    defineDocumentSpreadsheetTestAction,
    getBasicData,
    getBasicServerData,
    getDocumentBasicData,
} from "@documents_spreadsheet/../tests/helpers/data";
import { makeDocumentsSpreadsheetMockEnv } from "@documents_spreadsheet/../tests/helpers/model";
import {
    createSpreadsheetFromPivotView,
    spawnPivotViewForSpreadsheet,
} from "@documents_spreadsheet/../tests/helpers/pivot_helpers";
import { SpreadsheetAction } from "@documents_spreadsheet/bundle/actions/spreadsheet_action";
import { beforeEach, expect, getFixture, test } from "@odoo/hoot";
import { pointerDown } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { Model, constants, helpers } from "@odoo/o-spreadsheet";
import { selectCell, setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { Partner, Product, ResUsers } from "@spreadsheet/../tests/helpers/data";
import {
    getCellContent,
    getCellValue,
    getEvaluatedCell,
    getEvaluatedGrid,
} from "@spreadsheet/../tests/helpers/getters";
import { getZoneOfInsertedDataSource } from "@spreadsheet/../tests/helpers/pivot";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import {
    getSpreadsheetActionModel,
    prepareWebClientForSpreadsheet,
} from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import {
    contains,
    fields,
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    toggleMenu,
    toggleMenuItem,
    serverState,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";
import { WebClient } from "@web/webclient/webclient";

const { sanitizeSheetName, toCartesian, toZone } = helpers;

defineDocumentSpreadsheetModels();
defineDocumentSpreadsheetTestAction();

const { PIVOT_TABLE_CONFIG } = constants;

beforeEach(() => {
    ResUsers._records = getDocumentBasicData().models["res.users"].records;
});

function getGridIconEventPosition(model, xc) {
    const position = toCartesian(xc);
    const sheetId = model.getters.getActiveSheetId();
    const icon = model.getters.getCellIcons({ sheetId, ...position })[0];
    if (!icon) {
        throw new Error(`No icon inside cell ${xc}`);
    }
    const gridPosition = getFixture().querySelector(".o-grid-overlay").getBoundingClientRect();
    const gridOffset = model.getters.getGridOffset();
    const rect = model.getters.getCellIconRect(icon, model.getters.getRect(toZone(xc)));
    const x = rect.x + rect.width / 2 - gridOffset.x + gridPosition.x;
    const y = rect.y + rect.height / 2 - gridOffset.y + +gridPosition.y;
    return { x, y };
}

async function clickGridIcon(model, xc) {
    const { x, y } = getGridIconEventPosition(model, xc);
    await pointerDown(".o-grid-overlay", { position: { x, y } });
}

test("simple pivot export", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="foo" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A1")).toBe("");
    expect(getCellContent(model, "A2")).toBe("");
    expect(getCellContent(model, "A3")).toBe("=PIVOT.HEADER(1)");
    expect(getCellContent(model, "B1")).toBe("=PIVOT.HEADER(1)");
    expect(getCellContent(model, "B2")).toBe('=PIVOT.HEADER(1,"measure","foo:sum")');
    expect(getCellContent(model, "B3")).toBe('=PIVOT.VALUE(1,"foo:sum")');
});

test.tags("desktop");
test("open side panel in desktop mode", async () => {
    await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="foo" type="measure"/>
                        </pivot>`,
                "partner,false,search": /* xml */ `<search/>`,
            },
        },
    });
    expect(".o_spreadsheet_pivot_side_panel").toHaveCount(1);
});

test.tags("mobile");
test("don't open side panel in mobile mode", async () => {
    await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="foo" type="measure"/>
                        </pivot>`,
                "partner,false,search": /* xml */ `<search/>`,
            },
        },
    });
    expect(".o_spreadsheet_pivot_side_panel").toHaveCount(0);
});

test("simple pivot export with two measures", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="foo" type="measure"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "B1")).toBe("=PIVOT.HEADER(1)");
    expect(getCellContent(model, "B2")).toBe('=PIVOT.HEADER(1,"measure","foo:sum")');
    expect(getCellContent(model, "C2")).toBe('=PIVOT.HEADER(1,"measure","probability:avg")');
    expect(getCellContent(model, "B3")).toBe('=PIVOT.VALUE(1,"foo:sum")');
    expect(getCellContent(model, "C3")).toBe('=PIVOT.VALUE(1,"probability:avg")');
});

test("Insert in spreadsheet is disabled when data is empty", async () => {
    const data = getBasicData();
    data.partner.records = [];
    data.product.records = [];
    await makeDocumentsSpreadsheetMockEnv({ serverData: { models: data } });

    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
                <pivot>
                    <field name="foo" type="measure"/>
                </pivot>`,
    });
    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", true);
});

test("Insert in spreadsheet is disabled when no measure is specified", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
                <pivot>
                    <field name="foo" type="measure"/>
                </pivot>`,
    });

    await toggleMenu("Measures");
    await toggleMenuItem("Foo");
    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", true);
});

test("Insert in spreadsheet is disabled when same groupby occurs in both columns and rows", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
            <pivot>
                <field name="id" type="col"/>
                <field name="id" type="row"/>
                <field name="foo" type="measure"/>
            </pivot>`,
    });

    await toggleMenu("Measures");
    await toggleMenuItem("Foo");
    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", true);
});

test("Insert in spreadsheet is disabled when columns or rows contain duplicate groupbys", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
                <pivot>
                    <field name="id" type="col"/>
                    <field name="bar" type="row"/>
                    <field name="product_id" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
    });

    await toggleMenu("Measures");
    await toggleMenuItem("Probability");
    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", true);
});

test("Insert in spreadsheet is disabled when columns and rows both contains same groupby with different aggregator", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
                <pivot>
                    <field name="date" interval="year" type="col"/>
                    <field name="date" interval="month" type="row"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
    });

    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", true);
});

test("Can insert in spreadsheet when group by the same date fields with different aggregates", async () => {
    await mountView({
        type: "pivot",
        resModel: "partner",
        arch: /*xml*/ `
                <pivot>
                    <field name="date" interval="year" type="col"/>
                    <field name="date" interval="month" type="col"/>
                    <field name="probability" type="measure"/>
                </pivot>`,
    });

    expect("button.o_pivot_add_spreadsheet").toHaveProperty("disabled", false);
});

test("groupby date field without interval defaults to month", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <!-- no interval specified -->
                            <field name="date" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    const pivot = model.getters.getPivotCoreDefinition(pivotId);
    expect(pivot).toEqual({
        columns: [{ fieldName: "foo" }],
        context: {},
        domain: [],
        measures: [{ id: "probability:avg", fieldName: "probability", aggregator: "avg" }],
        model: "partner",
        rows: [{ fieldName: "date", granularity: "month" }],
        name: "Partners by Foo",
        type: "ODOO",
    });
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"date:month",DATE(2016,4,1))');
    expect(getCellContent(model, "A4")).toBe('=PIVOT.HEADER(1,"date:month",DATE(2016,10,1))');
    expect(getCellContent(model, "A5")).toBe('=PIVOT.HEADER(1,"date:month",DATE(2016,12,1))');
    expect(getCellContent(model, "B3")).toBe(
        '=PIVOT.VALUE(1,"probability:avg","date:month",DATE(2016,4,1),"foo",1)'
    );
    expect(getCellContent(model, "B4")).toBe(
        '=PIVOT.VALUE(1,"probability:avg","date:month",DATE(2016,10,1),"foo",1)'
    );
    expect(getCellContent(model, "B5")).toBe(
        '=PIVOT.VALUE(1,"probability:avg","date:month",DATE(2016,12,1),"foo",1)'
    );
    expect(getEvaluatedCell(model, "A3").formattedValue).toBe("April 2016");
    expect(getEvaluatedCell(model, "A4").formattedValue).toBe("October 2016");
    expect(getEvaluatedCell(model, "A5").formattedValue).toBe("December 2016");
    expect(getEvaluatedCell(model, "B3").formattedValue).toBe("");
    expect(getEvaluatedCell(model, "B4").formattedValue).toBe("11.00");
    expect(getEvaluatedCell(model, "B5").formattedValue).toBe("");

    setCellContent(model, "B4", '=PIVOT.VALUE(1,"probability:avg","date",DATE(2016,10,1),"foo",1)');
    expect(getEvaluatedCell(model, "B4").formattedValue).toBe("11.00");
});

test("pivot with one level of group bys", async () => {
    const { model } = await createSpreadsheetFromPivotView();
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"bar",FALSE)');
    expect(getCellContent(model, "A4")).toBe('=PIVOT.HEADER(1,"bar",TRUE)');
    expect(getCellContent(model, "A5")).toBe("=PIVOT.HEADER(1)");
    expect(getCellContent(model, "B2")).toBe(
        '=PIVOT.HEADER(1,"foo",1,"measure","probability:avg")'
    );
    expect(getCellContent(model, "C3")).toBe(
        '=PIVOT.VALUE(1,"probability:avg","bar",FALSE,"foo",2)'
    );
    expect(getCellContent(model, "F5")).toBe('=PIVOT.VALUE(1,"probability:avg")');
});

test("groupby date field on row gives correct name", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot string="Partners">
                            <field name="date" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    const pivot = model.getters.getPivotCoreDefinition(pivotId);
    expect(pivot).toEqual({
        columns: [],
        context: {},
        domain: [],
        measures: [{ id: "probability:avg", fieldName: "probability", aggregator: "avg" }],
        model: "partner",
        rows: [{ fieldName: "date", granularity: "month" }],
        name: "Partners by Date",
        type: "ODOO",
    });
});

test("pivot with two levels of group bys in rows", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="bar" type="row"/>
                            <field name="product_id" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"bar",FALSE)');
    expect(getCellContent(model, "A4")).toBe('=PIVOT.HEADER(1,"bar",FALSE,"product_id",41)');
    expect(getCellContent(model, "A5")).toBe('=PIVOT.HEADER(1,"bar",TRUE)');
    expect(getCellContent(model, "A6")).toBe('=PIVOT.HEADER(1,"bar",TRUE,"product_id",37)');
    expect(getCellContent(model, "A7")).toBe('=PIVOT.HEADER(1,"bar",TRUE,"product_id",41)');
    expect(getCellContent(model, "A8")).toBe("=PIVOT.HEADER(1)");
});

test("verify that there is a record for an undefined many2one header", async () => {
    const data = getBasicData();

    data.partner.records = [
        {
            id: 1,
            foo: 12,
            bar: true,
            date: "2016-04-14",
            product_id: false,
            probability: 10,
        },
    ];

    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: data,
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="product_id" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"product_id",FALSE)');
});

test("undefined date is inserted in pivot", async () => {
    const data = getBasicData();
    data.partner.records = [
        {
            id: 1,
            foo: 12,
            bar: true,
            date: false,
            product_id: 37,
            probability: 10,
        },
    ];

    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: data,
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="date" interval="day" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"date:day",FALSE)');
});

test("pivot with two levels of group bys in cols", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="bar" type="col"/>
                            <field name="product_id" type="col"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A1")).toBe("");
    expect(getCellContent(model, "B1")).toBe('=PIVOT.HEADER(1,"bar",FALSE)');
    expect(getCellContent(model, "B2")).toBe('=PIVOT.HEADER(1,"bar",FALSE,"product_id",41)');
    expect(getCellContent(model, "B3")).toBe(
        '=PIVOT.HEADER(1,"bar",FALSE,"product_id",41,"measure","probability:avg")'
    );
    expect(getCellContent(model, "C1")).toBe('=PIVOT.HEADER(1,"bar",TRUE)');
    expect(getCellContent(model, "C2")).toBe('=PIVOT.HEADER(1,"bar",TRUE,"product_id",37)');
    expect(getCellContent(model, "C3")).toBe(
        '=PIVOT.HEADER(1,"bar",TRUE,"product_id",37,"measure","probability:avg")'
    );
    expect(getCellContent(model, "D2")).toBe('=PIVOT.HEADER(1,"bar",TRUE,"product_id",41)');
    expect(getCellContent(model, "D3")).toBe(
        '=PIVOT.HEADER(1,"bar",TRUE,"product_id",41,"measure","probability:avg")'
    );
});

test("pivot with count as measure", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
        actions: async (target) => {
            await toggleMenu("Measures");
            await toggleMenuItem("Count");
        },
    });
    expect(getCellContent(model, "C2")).toBe('=PIVOT.HEADER(1,"measure","__count")');
    expect(getCellContent(model, "C3")).toBe('=PIVOT.VALUE(1,"__count")');
});

test("pivot with two levels of group bys in cols with not enough cols", async () => {
    const data = getBasicData();
    // add many values in a subgroup
    for (let i = 0; i < 70; i++) {
        Product._records.push({
            id: i + 9999,
            display_name: i.toString(),
        });
        Partner._records.push({
            id: i + 9999,
            bar: i % 2 === 0,
            product_id: i + 9999,
            probability: i,
        });
    }
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: data,
            views: {
                "partner,false,pivot": /* xml */ `
                            <pivot>
                                <field name="bar" type="col"/>
                                <field name="product_id" type="col"/>
                                <field name="foo" type="row"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
            },
        },
    });
    // 72 products * 1 groups + 1 row header + 1 total col
    expect(model.getters.getNumberCols(model.getters.getActiveSheetId())).toBe(75);
});

test("groupby week is sorted", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot string="Partners">
                            <field name="foo" type="col"/>
                            <field name="date" interval="week" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A3")).toBe(`=PIVOT.HEADER(1,"date:week","15/2016")`);
    expect(getCellContent(model, "A4")).toBe(`=PIVOT.HEADER(1,"date:week","43/2016")`);
    expect(getCellContent(model, "A5")).toBe(`=PIVOT.HEADER(1,"date:week","49/2016")`);
    expect(getCellContent(model, "A6")).toBe(`=PIVOT.HEADER(1,"date:week","50/2016")`);
});

test("Can save a pivot in a new spreadsheet", async () => {
    const serverData = {
        models: getBasicData(),
        views: {
            "partner,false,pivot": /* xml */ `
                 <pivot string="Partners">
                     <field name="probability" type="measure"/>
                 </pivot>`,
        },
    };
    await prepareWebClientForSpreadsheet();
    await makeDocumentsSpreadsheetMockEnv({
        serverData,
        mockRPC: function (route, args) {
            if (route.includes("get_spreadsheets_to_display")) {
                return [{ id: 1, name: "My Spreadsheet" }];
            }
            if (args.method === "action_open_new_spreadsheet") {
                expect.step("action_open_new_spreadsheet");
            }
        },
    });
    await mountWithCleanup(WebClient);

    await getService("action").doAction({
        res_model: "partner",
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
    });
    const target = getFixture();
    const insertButton = target.querySelector("button.o_pivot_add_spreadsheet");
    expect(insertButton.parentElement.dataset.tooltip).toBe(undefined);
    await contains(insertButton).click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    expect.verifySteps(["action_open_new_spreadsheet"]);
});

test.tags("desktop");
test("Can save a pivot in existing spreadsheet", async () => {
    const serverData = {
        models: getBasicData(),
        views: {
            "partner,false,pivot": /* xml */ `
                    <pivot>
                        <field name="probability" type="measure"/>
                    </pivot>`,
        },
    };
    await prepareWebClientForSpreadsheet();
    onRpc("/web/action/load", async () => {
        expect.step("write");
        return { id: 1, type: "ir.actions.act_window_close" };
    });
    onRpc("/spreadsheet/data/*", () => expect.step("/spreadsheet/data/"));
    await makeDocumentsSpreadsheetMockEnv({
        serverData,
        mockRPC: function (route, args) {
            if (args.model === "documents.document") {
                switch (args.method) {
                    case "get_spreadsheets_to_display":
                        return [{ id: 1, name: "My Spreadsheet" }];
                }
            }
        },
    });
    await mountWithCleanup(WebClient);

    await getService("action").doAction({
        res_model: "partner",
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
    });
    await contains(".o_pivot_add_spreadsheet").click();
    await contains(".o-spreadsheet-grid div[data-id='2']").click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    await animationFrame(); // Wait for the mounted to be executed
    expect(".o_spreadsheet_pivot_side_panel").toHaveCount(1);
    await getService("action").doAction(1); // leave the spreadsheet action
    expect.verifySteps(["/spreadsheet/data/", "write"]);
});

test("Add pivot sheet at the end of existing sheets", async () => {
    const model = new Model();
    model.dispatch("CREATE_SHEET", { sheetId: "42", position: 1, name: "My Sheet" });
    const models = getBasicData();
    models["documents.document"].records = [
        {
            spreadsheet_data: JSON.stringify(model.exportData()),
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
    await prepareWebClientForSpreadsheet();
    await makeDocumentsSpreadsheetMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "partner",
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
    });
    const fixture = getFixture();
    await contains(".o_pivot_add_spreadsheet").click();
    await contains(".o-spreadsheet-grid div[data-id='456']").click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    await animationFrame(); // Wait for the mounted to be executed
    expect(".o-sheet").toHaveCount(3, { message: "it should have a third sheet" });
    const sheets = fixture.querySelectorAll(".o-sheet");
    const activeSheet = fixture.querySelector(".o-sheet.active");
    expect(activeSheet).toBe(sheets[2]);
    expect(sheets[0]).toHaveText("Sheet1");
    expect(sheets[1]).toHaveText("My Sheet");
    expect(sheets[2]).toHaveText("Partners by Foo (Pivot #1)");
});

test("Add pivot in spreadsheet with already the same sheet name", async () => {
    const model = new Model();
    const activeSheetId = model.getters.getActiveSheetId();
    model.dispatch("RENAME_SHEET", {
        sheetId: model.getters.getActiveSheetId(),
        oldName: model.getters.getSheetName(activeSheetId),
        newName: "Partners by Foo (Pivot #1)",
    });
    const models = getBasicData();
    models["documents.document"].records = [
        {
            spreadsheet_data: JSON.stringify(model.exportData()),
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
    await prepareWebClientForSpreadsheet();
    await makeDocumentsSpreadsheetMockEnv({ serverData });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "partner",
        type: "ir.actions.act_window",
        views: [[false, "pivot"]],
    });
    const fixture = getFixture();
    await contains(".o_pivot_add_spreadsheet").click();

    await contains(".o-spreadsheet-grid div[data-id='456']").click();
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    await animationFrame();
    expect(".o-sheet").toHaveCount(2, { message: "it should have a second sheet" });
    const sheets = fixture.querySelectorAll(".o-sheet");
    expect(sheets[0]).toHaveText("Partners by Foo (Pivot #1)");
    expect(sheets[1]).toHaveText("Sheet1");
});

test("pivot with a domain", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        domain: [["bar", "=", true]],
    });
    const domain = model.getters.getPivotCoreDefinition(pivotId).domain;
    expect(domain).toEqual([["bar", "=", true]], {
        message: "It should have the correct domain",
    });
    expect(getCellContent(model, "A3")).toBe(`=PIVOT.HEADER(1,"bar",TRUE)`);
    expect(getCellContent(model, "A4")).toBe(`=PIVOT.HEADER(1)`);
});

test("pivot with a contextual domain", async () => {
    const uid = user.userId;
    const serverData = getBasicServerData();
    serverData.models.partner.records = [
        {
            id: 1,
            probability: 0.5,
            foo: uid,
            bar: true,
        },
    ];
    serverData.views["partner,false,search"] = /* xml */ `
            <search>
                <filter string="Filter" name="filter" domain="[('foo', '=', uid)]"/>
            </search>
        `;
    serverData.views["partner,false,pivot"] = /* xml */ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>
        `;
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData,
        additionalContext: { search_default_filter: 1 },
        mockRPC: function (route, args) {
            if (args.method === "formatted_read_grouping_sets") {
                expect(args.kwargs.domain).toEqual([["foo", "=", uid]], {
                    message: "data should be fetched with the evaluated the domain",
                });
                expect.step("formatted_read_grouping_sets");
            }
        },
    });
    const domain = model.getters.getPivotCoreDefinition(pivotId).domain;
    expect(domain).toBe('[("foo", "=", uid)]', {
        message: "It should have the raw domain string",
    });
    expect(model.exportData().pivots[pivotId].domain).toBe('[("foo", "=", uid)]', {
        message: "domain is exported with the dynamic value",
    });
    expect.verifySteps(["formatted_read_grouping_sets", "formatted_read_grouping_sets"]);
});

test("pivot with a quote in name", async function () {
    const data = getBasicData();
    Product._records.push({
        id: 42,
        display_name: `name with "`,
    });
    const { model } = await createSpreadsheetFromPivotView({
        model: "product",
        serverData: {
            models: data,
            views: {
                "product,false,pivot": /*xml*/ `
                        <pivot>
                            <field name="display_name" type="col"/>
                            <field name="id" type="row"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "B1")).toBe(`=PIVOT.HEADER(1,"display_name","name with \\"")`);
});

test("group by related field with archived record", async function () {
    // TODOAFTERSPLIT this doesn't seem to have any archived record
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="product_id" type="col"/>
                            <field name="name" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "B1")).toBe(`=PIVOT.HEADER(1,"product_id",37)`);
    expect(getCellContent(model, "C1")).toBe(`=PIVOT.HEADER(1,"product_id",41)`);
    expect(getCellContent(model, "D1")).toBe(`=PIVOT.HEADER(1)`);
});

test("group by regular field with archived record", async function () {
    Partner._records[0].active = false;
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                            <field name="product_id" type="col"/>
                            <field name="foo" type="row"/>
                            <field name="probability" type="measure"/>
                        </pivot>`,
            },
        },
    });
    expect(getCellContent(model, "A3")).toBe(`=PIVOT.HEADER(1,"foo",1)`);
    expect(getCellContent(model, "A4")).toBe(`=PIVOT.HEADER(1,"foo",2)`);
    expect(getCellContent(model, "A5")).toBe(`=PIVOT.HEADER(1,"foo",17)`);
    expect(getCellContent(model, "A6")).toBe(`=PIVOT.HEADER(1)`);
});

test("Columns of newly inserted pivot are auto-resized", async function () {
    const data = getBasicData();
    Partner._fields.probability = fields.Float({
        string: "Probability with a super long name",
        searchable: true,
        store: true,
        aggregator: "avg",
        groupable: false,
    });
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            ...getBasicServerData(),
            models: data,
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const defaultColSize = 96;
    expect(model.getters.getColSize(sheetId, 1) > defaultColSize).toBe(true, {
        message: "Column should be resized",
    });
});

test("user related context is not saved in the spreadsheet", async function () {
    serverState.companies = [{ id: 15, name: "Hermit" }];
    const userCtx = user.context;
    patchWithCleanup(user, {
        get context() {
            return Object.assign({}, userCtx, {
                allowed_company_ids: [15],
                tz: "bx",
                lang: "FR",
                uid: 4,
            });
        },
    });
    patchWithCleanup(user, { userId: 4 });
    const context = {
        ...user.context,
        default_stage_id: 5,
    };
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        additionalContext: context,
    });
    expect(model.exportData().pivots[pivotId].context).toEqual(
        {
            default_stage_id: 5,
        },
        { message: "user related context is not stored in context" }
    );
});

test("pivot related context is not saved in the spreadsheet", async function () {
    const context = {
        pivot_row_groupby: ["foo"],
        pivot_column_groupby: ["bar"],
        pivot_measures: ["probability"],
        default_stage_id: 5,
    };
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        additionalContext: context,
        actions: async (target) => {
            await toggleMenu("Measures");
            await toggleMenuItem("Count");
        },
        mockRPC: function (route, args) {
            if (args.method === "formatted_read_grouping_sets") {
                expect.step(args.kwargs.aggregates.join(","));
            }
        },
    });
    expect.verifySteps([
        // initial view
        "probability:avg,__count",
        // adding count in the view
        "probability:avg,__count",
        // loaded in the spreadsheet
        "probability:avg,__count",
    ]);
    expect(model.exportData().pivots[pivotId].context).toEqual(
        {
            default_stage_id: 5,
        },
        { message: "pivot related context is not stored in context" }
    );
});

test("sort first pivot column (ascending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        actions: async (target) => {
            await contains("thead .o_pivot_measure_row").click();
        },
    });
    expect(getCellValue(model, "A3")).toBe("No");
    expect(getCellValue(model, "A4")).toBe("Yes");
    expect(getCellValue(model, "B3")).toBe("");
    expect(getCellValue(model, "B4")).toBe(11);
    expect(getCellValue(model, "C3")).toBe(15);
    expect(getCellValue(model, "C4")).toBe("");
    expect(getCellValue(model, "F3")).toBe(15);
    expect(getCellValue(model, "F4")).toBe(116);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [{ field: "foo", value: 1, type: "integer" }],
        measure: "probability:avg",
        order: "asc",
    });
});

test("sort first pivot column (descending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        actions: async (target) => {
            await contains("thead .o_pivot_measure_row").click(); // first click toggles ascending
            await contains("thead .o_pivot_measure_row").click(); // second is descending
        },
    });
    expect(getCellValue(model, "A3")).toBe("Yes");
    expect(getCellValue(model, "A4")).toBe("No");
    expect(getCellValue(model, "B3")).toBe(11);
    expect(getCellValue(model, "B4")).toBe("");
    expect(getCellValue(model, "C3")).toBe("");
    expect(getCellValue(model, "C4")).toBe(15);
    expect(getCellValue(model, "F3")).toBe(116);
    expect(getCellValue(model, "F4")).toBe(15);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [{ field: "foo", value: 1, type: "integer" }],
        measure: "probability:avg",
        order: "desc",
    });
});

test("sort second pivot column (ascending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        actions: async (target) => {
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click();
        },
    });
    expect(getCellValue(model, "A3")).toBe("Yes");
    expect(getCellValue(model, "A4")).toBe("No");
    expect(getCellValue(model, "B3")).toBe(11);
    expect(getCellValue(model, "B4")).toBe("");
    expect(getCellValue(model, "C3")).toBe("");
    expect(getCellValue(model, "C4")).toBe(15);
    expect(getCellValue(model, "F3")).toBe(116);
    expect(getCellValue(model, "F4")).toBe(15);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [{ field: "foo", value: 2, type: "integer" }],
        measure: "probability:avg",
        order: "asc",
    });
});

test("sort second pivot column (descending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        actions: async (target) => {
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click(); // first click toggles ascending
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click(); // second is descending
        },
    });
    expect(getCellValue(model, "A3")).toBe("No");
    expect(getCellValue(model, "A4")).toBe("Yes");
    expect(getCellValue(model, "B3")).toBe("");
    expect(getCellValue(model, "B4")).toBe(11);
    expect(getCellValue(model, "C3")).toBe(15);
    expect(getCellValue(model, "C4")).toBe("");
    expect(getCellValue(model, "F3")).toBe(15);
    expect(getCellValue(model, "F4")).toBe(116);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [{ field: "foo", value: 2, type: "integer" }],
        measure: "probability:avg",
        order: "desc",
    });
});

test("sort second pivot measure (ascending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot string="Partners">
                            <field name="product_id" type="row"/>
                            <field name="probability" type="measure"/>
                            <field name="foo" type="measure"/>
                        </pivot>`,
            },
        },
        actions: async (target) => {
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click();
        },
    });
    expect(getCellValue(model, "A3")).toBe("xphone");
    expect(getCellValue(model, "A4")).toBe("xpad");
    expect(getCellValue(model, "B3")).toBe(10);
    expect(getCellValue(model, "B4")).toBe(121);
    expect(getCellValue(model, "C3")).toBe(12);
    expect(getCellValue(model, "C4")).toBe(20);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [],
        measure: "foo:sum",
        order: "asc",
    });
});

test("sort second pivot measure (descending)", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot string="Partners">
                            <field name="product_id" type="row"/>
                            <field name="probability" type="measure"/>
                            <field name="foo" type="measure"/>
                        </pivot>`,
            },
        },
        actions: async (target) => {
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click();
            await contains(target.querySelectorAll("thead .o_pivot_measure_row")[1]).click();
        },
    });
    expect(getCellValue(model, "A3")).toBe("xpad");
    expect(getCellValue(model, "A4")).toBe("xphone");
    expect(getCellValue(model, "B3")).toBe(121);
    expect(getCellValue(model, "B4")).toBe(10);
    expect(getCellValue(model, "C3")).toBe(20);
    expect(getCellValue(model, "C4")).toBe(12);
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toEqual({
        domain: [],
        measure: "foo:sum",
        order: "desc",
    });
});

test("sorting on a date column works", async () => {
    patchWithCleanup(user, { tz: "UTC" });
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        actions: async (target) => {
            await contains("thead .o_pivot_measure_row").click();
        },
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                    <pivot default_order="probability desc">
                        <field name="create_date" interval="year" type="col"/>
                        <field name="create_date" interval="quarter" type="col"/>
                        <field name="create_date" interval="month" type="col"/>
                        <field name="create_date" interval="week" type="col"/>
                        <field name="create_date" interval="day" type="col"/>
                        <field name="product_id" type="row"/>
                        <field name="foo" type="measure"/>
                    </pivot>`,
            },
        },
    });
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn.domain).toMatchObject([
        { field: "create_date:year", value: 2006 },
        { field: "create_date:quarter", value: "4/2005" },
        { field: "create_date:month", value: "12/2005" },
        { field: "create_date:week", value: "1/2006" },
        { field: "create_date:day", value: 38719 },
    ]);
});

test("remove sorting if measure is removed", async () => {
    const { model, pivotId } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                    <pivot default_order="probability desc">
                        <field name="product_id" type="row"/>
                        <field name="probability" type="measure"/>
                        <field name="foo" type="measure"/>
                    </pivot>`,
            },
        },
        actions: async (target) => {
            await toggleMenu("Measures");
            await toggleMenuItem("Probability"); // remove probability measure
        },
    });
    expect(model.getters.getPivotCoreDefinition(pivotId).sortedColumn).toBe(undefined);
});

test("search view with group by and additional row group", async () => {
    const { model } = await createSpreadsheetFromPivotView({
        additionalContext: { search_default_group_name: true },
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                        <pivot>
                        </pivot>`,
                "partner,false,search": /* xml */ `
                    <search>
                        <group>
                            <filter name="group_name" context="{'group_by':'name'}"/>
                            <filter name="group_foo" context="{'group_by':'foo'}"/>
                        </group>
                    </search>
                `,
            },
        },
        actions: async (target) => {
            await contains(target.querySelectorAll("tbody .o_pivot_header_cell_closed")[0]).click();
            // group by foo
            await contains(".dropdown-menu span:nth-child(2)").click();
        },
    });
    expect(getCellContent(model, "A1")).toBe("");
    expect(getCellContent(model, "A2")).toBe("");
    expect(getCellContent(model, "A3")).toBe('=PIVOT.HEADER(1,"name","Raoul")');
    expect(getCellContent(model, "A4")).toBe('=PIVOT.HEADER(1,"name","Raoul","foo",12)');
    expect(getCellContent(model, "A5")).toBe('=PIVOT.HEADER(1,"name","Steven")');
    expect(getCellContent(model, "A6")).toBe('=PIVOT.HEADER(1,"name","Steven","foo",1)');
    expect(getCellContent(model, "A7")).toBe('=PIVOT.HEADER(1,"name","Taylor")');
    expect(getCellContent(model, "A8")).toBe('=PIVOT.HEADER(1,"name","Taylor","foo",17)');
    expect(getCellContent(model, "A9")).toBe('=PIVOT.HEADER(1,"name","Zara")');
    expect(getCellContent(model, "A10")).toBe('=PIVOT.HEADER(1,"name","Zara","foo",2)');
    expect(getCellContent(model, "B2")).toBe('=PIVOT.HEADER(1,"measure","__count")');
});

test("Pivot name can be changed from the dialog", async () => {
    await spawnPivotViewForSpreadsheet();

    let spreadsheetAction;
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            spreadsheetAction = this;
        },
    });
    await contains(document.body.querySelector(".o_pivot_add_spreadsheet")).click();
    await contains(".o-sp-dialog-meta-name .o_input").edit("New name");
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    const pivotId = model.getters.getPivotIds()[0];
    expect(model.getters.getPivotName(pivotId)).toBe("New name");
    expect(model.getters.getPivotDisplayName(pivotId)).toBe("(#1) New name");
});

test("Pivot name is not changed if the name is empty", async () => {
    await spawnPivotViewForSpreadsheet();

    let spreadsheetAction;
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            spreadsheetAction = this;
        },
    });
    await contains(document.body.querySelector(".o_pivot_add_spreadsheet")).click();
    document.body.querySelector(".o-sp-dialog-meta-name .o_input").value = "";
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    await animationFrame();
    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    const pivotId = model.getters.getPivotIds()[0];
    expect(model.getters.getPivotName(pivotId)).toBe("Partners by Foo");
});

test("Sheet is created when pivot name contains invalid characters", async () => {
    await spawnPivotViewForSpreadsheet();

    let spreadsheetAction;
    patchWithCleanup(SpreadsheetAction.prototype, {
        setup() {
            super.setup();
            spreadsheetAction = this;
        },
    });
    await contains(document.body.querySelector(".o_pivot_add_spreadsheet")).click();
    const pivotName = "Do not keep Unsupported characters: '-:-*-?-\\-[-]-/";
    await contains(".o-sp-dialog-meta-name .o_input").edit(pivotName);
    await contains(".modal-content > .modal-footer > .btn-primary").click();
    const model = getSpreadsheetActionModel(spreadsheetAction);
    await waitForDataLoaded(model);
    const pivotId = model.getters.getPivotIds()[0];
    expect(model.getters.getPivotName(pivotId)).toBe(pivotName);
    expect(model.getters.getPivotDisplayName(pivotId)).toBe(`(#1) ${pivotName}`);
    const sanitizedSheetName = sanitizeSheetName(pivotName);
    expect(model.getters.getSheetName(model.getters.getActiveSheetId())).toBe(
        `${sanitizedSheetName} (Pivot #1)`
    );
});

test("Check pivot measures with m2o field", async function () {
    const data = getBasicData();
    Partner._records.push(
        { active: true, id: 5, foo: 12, bar: true, product_id: 37, probability: 50 },
        { active: true, id: 6, foo: 17, bar: true, product_id: 41, probability: 12 },
        { active: true, id: 7, foo: 17, bar: true, product_id: 37, probability: 13 },
        { active: true, id: 8, foo: 17, bar: true, product_id: 37, probability: 14 }
    );
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: data,
            views: {
                "partner,false,pivot": `
                            <pivot string="Partners">
                                <field name="foo" type="col"/>
                                <field name="bar" type="row"/>
                                <field name="product_id" type="measure"/>
                            </pivot>`,
            },
        },
    });
    expect(getCellValue(model, "B4")).toBe(1, {
        message: "[Cell B3] There is one distinct product for 'foo - 1' and 'bar - true'",
    });
    expect(getCellValue(model, "D4")).toBe(1, {
        message: "[Cell C3] There is one distinct product for 'foo - 12' and 'bar - true'",
    });
    expect(getCellValue(model, "E4")).toBe(2, {
        message: "[Cell D3] There are two distinct products for 'foo - 17' and 'bar - true'",
    });
});

test("Pivot export from an action with an xml ID", async function () {
    const actionXmlId = "spreadsheet.partner_action";
    const { model, pivotId } = await createSpreadsheetFromPivotView({ actionXmlId });
    expect(model.getters.getPivotCoreDefinition(pivotId).actionXmlId).toEqual(
        "spreadsheet.partner_action"
    );
});

test("Test Autofill component", async function () {
    const { model } = await createSpreadsheetFromPivotView();
    selectCell(model, "A3");
    setCellContent(model, "B3", "");
    await pointerDown(".o-autofill-handler");
    await animationFrame();
    // dispatching the underlying command by hand because the dragndrop in o_spreadsheet.js
    // does not react well to the events
    model.dispatch("AUTOFILL_SELECT", { col: 1, row: 2 });
    await animationFrame();
    expect(".o-autofill-nextvalue:first").toHaveText("1");
    expect(getCellContent(model, "B2")).toBe(
        `=PIVOT.HEADER(1,"foo",1,"measure","probability:avg")`
    );
});

test("Inserted pivot is inserted with a table", async function () {
    const { model } = await createSpreadsheetFromPivotView();
    const sheetId = model.getters.getActiveSheetId();
    const [pivotId] = model.getters.getPivotIds();
    const pivotZone = getZoneOfInsertedDataSource(model, "pivot", pivotId);
    const tables = model.getters.getTables(sheetId);

    expect(tables.length).toBe(1);
    expect(tables[0].range.zone).toEqual(pivotZone);
    expect(tables[0].type).toBe("static");
    expect(tables[0].config).toEqual({ ...PIVOT_TABLE_CONFIG, numberOfHeaders: 1 });
});

test("The table has the correct number of headers when inserting a pivot", async function () {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                            <pivot>
                                <field name="date" interval="year" type="col"/>
                                <field name="date" interval="month" type="col"/>
                                <field name="date" interval="day" type="col"/>
                                <field name="probability" type="row"/>
                                <field name="foo" type="measure"/>
                            </pivot>`,
            },
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const tables = model.getters.getTables(sheetId);
    const [pivotId] = model.getters.getPivotIds();
    const pivotZone = getZoneOfInsertedDataSource(model, "pivot", pivotId);

    expect(tables[0].range.zone).toEqual(pivotZone);
    expect(tables[0].type).toBe("static");
    expect(tables[0].config.numberOfHeaders).toBe(3);
});

test("Can collapse pivot header group", async function () {
    const { model } = await createSpreadsheetFromPivotView({
        serverData: {
            models: getBasicData(),
            views: {
                "partner,false,pivot": /* xml */ `
                            <pivot>
                                <field name="date" interval="year" type="col"/>
                                <field name="date" interval="month" type="col"/>
                                <field name="probability" type="measure"/>
                            </pivot>`,
                "partner,false,search": /* xml */ `<search/>`,
            },
        },
    });
    selectCell(model, "A20");
    await animationFrame();
    setCellContent(model, "A20", "=PIVOT(1)");
    await clickGridIcon(model, "B20");

    const [pivotId] = model.getters.getPivotIds();
    const definition = model.getters.getPivotCoreDefinition(pivotId);
    expect(definition.collapsedDomains).toEqual({
        COL: [[{ field: "date:year", value: 2016, type: "date" }]],
        ROW: [],
    });

    // prettier-ignore
    expect(getEvaluatedGrid(model, "A20:C23")).toEqual([
        ["Untitled by Date (Year)",         2016,           ""],
        ["",                                "",             "Total"],
        ["",                                "Probability",  "Probability"],
        ["Total",                           131,            131],
    ]);
});
