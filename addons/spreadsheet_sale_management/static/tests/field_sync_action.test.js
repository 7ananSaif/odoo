import { expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { defineModels, onRpc } from "@web/../tests/web_test_helpers";
import { x2ManyCommands } from "@web/core/orm_service";

import { mailModels } from "@mail/../tests/mail_test_helpers";

import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { getCellContent } from "@spreadsheet/../tests/helpers/getters";

import { helpers, stores } from "@odoo/o-spreadsheet";
import { addFieldSync } from "./helpers/commands";
import {
    defineSpreadsheetSaleModels,
    getSaleOrderSpreadsheetData,
    SaleOrderSpreadsheet,
} from "./helpers/data";
import { mountSaleOrderSpreadsheetAction } from "./helpers/webclient_helpers";

const { HighlightStore, DelayedHoveredCellStore } = stores;
const { toZone } = helpers;

defineSpreadsheetSaleModels();
defineModels(mailModels);

test("write on sale order when leaving action", async () => {
    const orderId = 1;
    onRpc("sale.order", "write", ({ args }) => {
        const [orderIds, vals] = args;
        expect(orderIds).toEqual([orderId]);
        expect(vals).toEqual({
            order_line: [
                x2ManyCommands.update(1, {
                    product_uom_qty: 1000,
                }),
            ],
        });
        expect.step("write-sale-order");
        return true;
    });
    const { model } = await mountSaleOrderSpreadsheetAction();
    addFieldSync(model, "A1", "product_uom_qty", 0);
    setCellContent(model, "A1", "1000");
    await click("button:contains(Save in sale.order,1)");
    await animationFrame();
    expect.verifySteps(["write-sale-order"]);
});

test("don't write on sale order with no order_id param", async () => {
    onRpc("sale.order", "write", () => {
        expect.step("write-sale-order");
    });
    const spreadsheetId = 1;
    SaleOrderSpreadsheet._records = [
        {
            id: spreadsheetId,
            name: "My sale order spreadsheet",
            spreadsheet_data: JSON.stringify(getSaleOrderSpreadsheetData()),
            order_id: false,
        },
    ];
    const { model } = await mountSaleOrderSpreadsheetAction({ spreadsheetId });
    addFieldSync(model, "A1", "product_uom_qty", 0);
    setCellContent(model, "A1", "1000");
    expect("button:contains(Write to sale.order,1)").toHaveCount(0);
});

test("global filter initialized with orderId", async () => {
    const { model } = await mountSaleOrderSpreadsheetAction();
    const [filter] = model.getters.getGlobalFilters();
    expect(model.getters.getGlobalFilterValue(filter.id)).toEqual({ operator: "in", ids: [1] });
});

test("global filter initialized with orderId with old data version", async () => {
    const spreadsheetId = 1;
    const data = {
        version: "18.4.14",
        revisionId: "START_REVISION",
        sheets: [{ id: "sheet1" }],
        lists: {
            1: {
                columns: [],
                domain: [],
                model: "sale.order.line",
                context: {},
                orderBy: [],
                id: "1",
                name: "Sale order lines",
                fieldMatching: {
                    order_filter_id: {
                        chain: "order_id",
                        type: "many2one",
                    },
                },
            },
        },
        globalFilters: [
            {
                id: "order_filter_id",
                type: "relation",
                label: "Sales Order",
                modelName: "sale.order",
            },
        ],
    };
    const orderId = 1;
    SaleOrderSpreadsheet._records = [
        {
            id: spreadsheetId,
            name: "My sale order spreadsheet",
            spreadsheet_data: JSON.stringify(data),
            order_id: orderId,
        },
    ];
    const { model } = await mountSaleOrderSpreadsheetAction();
    const [filter] = model.getters.getGlobalFilters();
    expect(model.getters.getGlobalFilterValue(filter.id)).toEqual({
        operator: "in",
        ids: [orderId],
    });
});

test("auto resize list columns", async () => {
    onRpc("/spreadsheet/data/sale.order.spreadsheet/*", () => {
        const data = getSaleOrderSpreadsheetData();
        const commands = [
            {
                type: "RE_INSERT_ODOO_LIST",
                sheetId: data.sheets[0].id,
                col: 0,
                row: 0,
                id: "1",
                linesNumber: 20,
                columns: [{ name: "product_uom_qty", type: "float" }],
            },
        ];
        return {
            name: "my spreadsheet",
            data,
            isReadonly: false,
            revisions: [
                {
                    serverRevisionId: "START_REVISION",
                    nextRevisionId: "abcd",
                    version: "1",
                    type: "REMOTE_REVISION",
                    commands,
                },
            ],
        };
    });
    const { model } = await mountSaleOrderSpreadsheetAction();
    const sheetId = model.getters.getActiveSheetId();
    expect(getCellContent(model, "A1")).toBe('=ODOO.LIST.HEADER(1,"product_uom_qty")');
    expect(model.getters.getHeaderSize(sheetId, "COL", 0)).not.toBe(96);
    expect(model.getters.getHeaderSize(sheetId, "COL", 1)).toBe(96); // default width
});

test("hover field sync highlights matching list formulas", async () => {
    const { model, env } = await mountSaleOrderSpreadsheetAction();
    const hoverStore = env.getStore(DelayedHoveredCellStore);
    const highlightStore = env.getStore(HighlightStore);
    addFieldSync(model, "B1", "product_uom_qty", 0);
    setCellContent(model, "A1", '=ODOO.LIST(1,1,"product_uom_qty")');
    expect(highlightStore.highlights).toHaveLength(0);
    hoverStore.hover({ col: 1, row: 0 });
    expect(highlightStore.highlights).toHaveLength(1);
    expect(highlightStore.highlights[0].range.zone).toEqual(toZone("A1"));
    expect(highlightStore.highlights[0].color).toBe("#875A7B");
    expect(highlightStore.highlights[0].sheetId).toBe(model.getters.getActiveSheetId());

    // with computed list args
    setCellContent(model, "A1", "=ODOO.LIST(A2, A3, A4)");
    expect(highlightStore.highlights).toHaveLength(0);
    setCellContent(model, "A2", "1");
    setCellContent(model, "A3", "1");
    setCellContent(model, "A4", "product_uom_qty");
    hoverStore.hover({ col: 1, row: 0 });
    expect(highlightStore.highlights).toHaveLength(1);
    expect(highlightStore.highlights[0].range.zone).toEqual(toZone("A1"));
    expect(highlightStore.highlights[0].color).toBe("#875A7B");
    expect(highlightStore.highlights[0].sheetId).toBe(model.getters.getActiveSheetId());
});
