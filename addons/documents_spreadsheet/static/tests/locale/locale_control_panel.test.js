import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { onRpc } from "@web/../tests/web_test_helpers";

defineDocumentSpreadsheetModels();

describe.current.tags("desktop");

const en_US = {
    name: "English (US)",
    code: "en_US",
    thousandsSeparator: ",",
    decimalSeparator: ".",
    dateFormat: "m/d/yyyy",
    timeFormat: "hh:mm:ss a",
    formulaArgSeparator: ",",
};

const fr_FR = {
    name: "French",
    code: "fr_FR",
    thousandsSeparator: " ",
    decimalSeparator: ",",
    dateFormat: "dd/mm/yyyy",
    timeFormat: "hh:mm:ss",
    formulaArgSeparator: ";",
};

test("No locale icon if user locale matched spreadsheet locale", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        name: "Untitled spreadsheet",
        user_locale: en_US,
        data: {
            settings: { locale: en_US },
        },
    }));
    await createSpreadsheet();
    expect(".o-spreadsheet-topbar .fa-globe").not.toHaveCount();
});

test("No locale icon if no user locale is given", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        name: "Untitled spreadsheet",
        data: {
            settings: { locale: en_US },
        },
    }));
    await createSpreadsheet();
    expect(".o-spreadsheet-topbar .fa-globe").not.toHaveCount();
});

test("Different locales between user and spreadsheet: display icon as info", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        name: "Untitled spreadsheet",
        user_locale: fr_FR,
        data: {
            settungs: { locale: en_US },
        },
    }));
    await createSpreadsheet();
    expect(".o-spreadsheet-topbar .fa-globe.text-info").toHaveProperty(
        "title",
        "Difference between user locale (fr_FR) and spreadsheet locale (en_US). This spreadsheet is using the formats below:\n" +
            "- dates: m/d/yyyy\n" +
            "- numbers: 1,234,567.89"
    );
});

test("no warning with different locale codes but same formats", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        name: "Untitled spreadsheet",
        user_locale: { ...fr_FR, code: "fr_BE" },
        data: {
            settings: { locale: fr_FR },
        },
    }));
    await createSpreadsheet();
    expect(".o-spreadsheet-topbar .fa-globe").not.toHaveCount();
});

test("changing spreadsheet locale to user locale: remove icon", async function () {
    onRpc("/spreadsheet/data/*", () => ({
        name: "Untitled spreadsheet",
        user_locale: en_US,
        data: {
            settings: { locale: fr_FR },
        },
    }));
    const { model } = await createSpreadsheet();
    expect(".o-spreadsheet-topbar .fa-globe").toHaveCount(1);
    model.dispatch("UPDATE_LOCALE", { locale: en_US });
    await animationFrame();
    expect(".o-spreadsheet-topbar .fa-globe").not.toHaveCount();
});
