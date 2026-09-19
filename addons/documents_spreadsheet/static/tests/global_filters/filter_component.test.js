import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { describe, expect, test } from "@odoo/hoot";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

test("Filter component is visible even without data source", async function () {
    await createSpreadsheet();
    expect(".o_topbar_filter_icon").toHaveCount(1);
});
