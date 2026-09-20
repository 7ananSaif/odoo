import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";

import { stores } from "@odoo/o-spreadsheet";
import {
    createSpreadsheetWithPivot,
    insertPivotInSpreadsheet,
} from "@spreadsheet/../tests/helpers/pivot";
import { getBasicPivotArch, defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { makeStoreWithModel } from "@spreadsheet/../tests/helpers/stores";

describe.current.tags("headless");
defineSpreadsheetModels();

const { CellComposerStore } = stores;

test("PIVOT.VALUE.* autocomplete pivot id", async function () {
    const { model } = await createSpreadsheetWithPivot();
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    await insertPivotInSpreadsheet(model, "pivot2", { arch: getBasicPivotArch() });
    for (const func of ["PIVOT", "PIVOT.HEADER", "PIVOT.VALUE"]) {
        composer.startEdition(`=${func}(`);
        await animationFrame();
        const proposals = composer.autoCompleteProposals;
        expect(proposals).toEqual(
            [
                {
                    description: "Partner Pivot",
                    fuzzySearchKey: "1Partner Pivot",
                    htmlContent: [{ color: "#02c39a", value: "1" }],
                    text: "1",
                    alwaysExpanded: true,
                },
                {
                    description: "Partner Pivot",
                    fuzzySearchKey: "2Partner Pivot",
                    htmlContent: [{ color: "#02c39a", value: "2" }],
                    text: "2",
                    alwaysExpanded: true,
                },
            ],
            { message: `autocomplete proposals for ${func}` }
        );
        composer.insertAutoCompleteValue(proposals[0].text);
        await animationFrame();
        expect(composer.currentContent).toBe(`=${func}(1`);
        expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
        composer.cancelEdition();
    }
});

test("do not show autocomplete if pivot id already set", async function () {
    const { model } = await createSpreadsheetWithPivot();
    await insertPivotInSpreadsheet(model, "pivot2", { arch: getBasicPivotArch() });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    for (const func of ["PIVOT", "PIVOT.HEADER", "PIVOT.VALUE"]) {
        // id as a number
        composer.startEdition(`=${func}(1`);
        await animationFrame();
        expect(composer.isAutoCompleteDisplayed).toBe(false);
        composer.cancelEdition();

        // id as a string
        composer.startEdition(`=${func}("1"`);
        await animationFrame();
        expect(composer.isAutoCompleteDisplayed).toBe(false);
        composer.cancelEdition();
    }
});

test("PIVOT.VALUE measure", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
                <field name="__count" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition("=PIVOT.VALUE(1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "Probability",
            fuzzySearchKey: 'Probabilityprobability"probability:avg"',
            htmlContent: [{ color: "#00a82d", value: '"probability:avg"' }],
            text: '"probability:avg"',
        },
        {
            description: "Count",
            fuzzySearchKey: 'Count"__count"',
            htmlContent: [{ color: "#00a82d", value: '"__count"' }],
            text: '"__count"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability:avg"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE measure with the pivot id as a string", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE("1",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"probability:avg"']);
});

test("PIVOT.VALUE measure with pivot id that does not exists", async function () {
    const { model } = await createSpreadsheetWithPivot();
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition(`=PIVOT.VALUE(9999,`);
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("PIVOT.VALUE measure without any pivot id", async function () {
    const { model } = await createSpreadsheetWithPivot();
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition(`=PIVOT.VALUE(,`);
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("PIVOT.VALUE group with a single col group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "Product",
            fuzzySearchKey: 'Product"product_id"',
            htmlContent: [{ color: "#00a82d", value: '"product_id"' }],
            text: '"product_id"',
        },
        {
            description: "Product (positional)",
            fuzzySearchKey: 'Product"#product_id"',
            htmlContent: [{ color: "#00a82d", value: '"#product_id"' }],
            text: '"#product_id"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","product_id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE group with a pivot id as string", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE("1","probability",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
});

test("PIVOT.VALUE group with a single row group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "Product",
            fuzzySearchKey: 'Product"product_id"',
            htmlContent: [{ color: "#00a82d", value: '"product_id"' }],
            text: '"product_id"',
        },
        {
            description: "Product (positional)",
            fuzzySearchKey: 'Product"#product_id"',
            htmlContent: [{ color: "#00a82d", value: '"#product_id"' }],
            text: '"#product_id"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","product_id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("ODOO.VALUE group with a single date grouped by day", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row" interval="day"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "Date",
            fuzzySearchKey: 'Date"date:day"',
            htmlContent: [{ color: "#00a82d", value: '"date:day"' }],
            text: '"date:day"',
        },
        {
            description: "Date (positional)",
            fuzzySearchKey: 'Date"#date:day"',
            htmlContent: [{ color: "#00a82d", value: '"#date:day"' }],
            text: '"#date:day"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","date:day"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE group after a positional group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="date" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability", "#date:month", 1,');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
});

test("PIVOT.VALUE search field", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","prod');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
});

test("PIVOT.VALUE search field with both col and row group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="date" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    // (notice the space after the comma)
    composer.startEdition('=PIVOT.VALUE(1,"probability", ');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual([
        '"product_id"',
        '"date:month"',
        '"#product_id"',
        '"#date:month"',
    ]);
});

test("PIVOT.VALUE group with row and col groups for the first group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="date" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual([
        '"date:month"',
        '"product_id"',
        '"#date:month"',
        '"#product_id"',
    ]);
});

test("PIVOT.VALUE group with row and col groups for the col group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="date" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","product_id",1,');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"date:month"', '"#date:month"']);
});

test("PIVOT.VALUE group with two rows, on the first group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="date" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability", ,1,"date", "11/2020")');
    //..................................................^ the cursor is here
    composer.changeComposerCursorSelection(29, 29);
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
});

test("PIVOT.VALUE search a positional group", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","#pro');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"#product_id"']);
});

test("PIVOT.VALUE autocomplete relational field for group value", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","product_id",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "xphone",
            fuzzySearchKey: "37xphone",
            htmlContent: [{ color: "#02c39a", value: "37" }],
            text: "37",
        },
        {
            description: "xpad",
            fuzzySearchKey: "41xpad",
            htmlContent: [{ color: "#02c39a", value: "41" }],
            text: "41",
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","product_id",37');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE autocomplete date field for group value", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row" interval="month"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","date:month",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "April 2016",
            fuzzySearchKey: '"04/2016"April 2016',
            htmlContent: [{ color: "#00a82d", value: '"04/2016"' }],
            text: '"04/2016"',
        },
        {
            description: "October 2016",
            fuzzySearchKey: '"10/2016"October 2016',
            htmlContent: [{ color: "#00a82d", value: '"10/2016"' }],
            text: '"10/2016"',
        },
        {
            description: "December 2016",
            fuzzySearchKey: '"12/2016"December 2016',
            htmlContent: [
                {
                    color: "#00a82d",
                    value: '"12/2016"',
                },
            ],
            text: '"12/2016"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","date:month","04/2016"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE autocomplete date field with no specified granularity for group value", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","date:month",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals).toEqual([
        {
            description: "April 2016",
            fuzzySearchKey: '"04/2016"April 2016',
            htmlContent: [{ color: "#00a82d", value: '"04/2016"' }],
            text: '"04/2016"',
        },
        {
            description: "October 2016",
            fuzzySearchKey: '"10/2016"October 2016',
            htmlContent: [{ color: "#00a82d", value: '"10/2016"' }],
            text: '"10/2016"',
        },
        {
            description: "December 2016",
            fuzzySearchKey: '"12/2016"December 2016',
            htmlContent: [
                {
                    color: "#00a82d",
                    value: '"12/2016"',
                },
            ],
            text: '"12/2016"',
        },
    ]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.VALUE(1,"probability","date:month","04/2016"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.VALUE autocomplete field after a date field", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row" interval="month"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","date:month","11/2020",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
});

test("PIVOT.VALUE autocomplete field after a date field with granularity in arch but not in formula", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row" interval="month"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","date","11/2020",');
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("PIVOT.VALUE autocomplete field after a date field without granularity", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="date" type="row"/>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","date","11/2020",');
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("PIVOT.VALUE no autocomplete for positional group field", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="row"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.VALUE(1,"probability","#product_id",');
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("PIVOT.HEADER first field", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition("=PIVOT.HEADER(1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.HEADER(1,"product_id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.HEADER search field", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.HEADER(1,"pro');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(['"product_id"', '"#product_id"']);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.HEADER(1,"product_id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("PIVOT.HEADER group value", async function () {
    const { model } = await createSpreadsheetWithPivot({
        arch: /*xml*/ `
            <pivot>
                <field name="product_id" type="col"/>
                <field name="probability" type="measure"/>
            </pivot>`,
    });
    const { store: composer } = makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=PIVOT.HEADER(1,"product_id",');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    expect(proposals.map((p) => p.text)).toEqual(["37", "41"]);
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=PIVOT.HEADER(1,"product_id",37');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});
