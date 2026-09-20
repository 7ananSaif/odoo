import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { stores } from "@odoo/o-spreadsheet";
import { Partner, Product, defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import {
    insertListInSpreadsheet,
    createSpreadsheetWithList,
} from "@spreadsheet/../tests/helpers/list";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { makeStore, makeStoreWithModel } from "@spreadsheet/../tests/helpers/stores";

describe.current.tags("headless");
defineSpreadsheetModels();

const { CellComposerStore } = stores;

test("ODOO.LIST id", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    await animationFrame();
    for (const formula of ["=ODOO.LIST(", "=ODOO.LIST( ", "=ODOO.LIST.HEADER("]) {
        composer.startEdition(formula);
        await animationFrame();
        const proposals = composer.autoCompleteProposals;
        expect(proposals).toEqual([
            {
                description: "List",
                fuzzySearchKey: "1List",
                htmlContent: [{ color: "#02c39a", value: "1" }],
                text: "1",
                alwaysExpanded: true,
            },
        ]);
        composer.cancelEdition();
    }
});

test("ODOO.LIST id exact match", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST(1");
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("ODOO.LIST field name", async function () {
    const { model } = await createModelWithDataSource();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["product_id", "bar"],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST(1,1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Partner._fields);
    expect(proposals.map((p) => p.text)).toEqual(
        allFields.map((field) => `"${field}"`),
        { message: "all fields are proposed, quoted" }
    );
    // check completely only the first one
    expect(proposals[0]).toEqual({
        description: "Id",
        fuzzySearchKey: 'Id"id"',
        htmlContent: [{ color: "#00a82d", value: '"id"' }],
        text: '"id"',
    });
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=ODOO.LIST(1,1,"id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("ODOO.LIST related field name", async function () {
    const { model } = await createSpreadsheetWithList();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=ODOO.LIST(1,1,"product_id"');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Product._fields);
    expect(proposals.map((p) => p.text).sort(String.localeCompare)).toEqual(
        allFields.map((field) => `"product_id.${field}"`).sort(String.localeCompare),
        { message: "all fields are proposed, quoted" }
    );
    // check completely only the first one
    expect(proposals[0]).toEqual({
        description: "Id",
        fuzzySearchKey: 'Id"product_id.id"',
        htmlContent: [{ color: "#00a82d", value: '.id"' }],
        text: '"product_id.id"',
    });
    composer.insertAutoCompleteValue(proposals[0].text);
    await animationFrame();
    expect(composer.currentContent).toBe('=ODOO.LIST(1,1,"product_id.id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("ODOO.LIST invalid related field path", async function () {
    const { model } = await createSpreadsheetWithList();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=ODOO.LIST(1,1,"product_id.name.name"');
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("ODOO.LIST.HEADER field name", async function () {
    const { model } = await createModelWithDataSource();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["product_id", "bar"],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST.HEADER(1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Partner._fields);
    expect(proposals.map((p) => p.text)).toEqual(
        allFields.map((field) => `"${field}"`),
        { message: "all fields are proposed, quoted" }
    );
});

test("ODOO.LIST field name with invalid list id", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: ["foo", "bar", "date", "product_id"],
    });
    await animationFrame();
    for (const listId of ["", "0", "42"]) {
        composer.startEdition(`=ODOO.LIST(${listId},1,`);
        await animationFrame();
        expect(composer.isAutoCompleteDisplayed).toBe(false);
        composer.cancelEdition();
    }
});
