import { expect, test } from "@odoo/hoot";
import { registries } from "@odoo/o-spreadsheet";
import { setSelection, setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { getCellValue } from "@spreadsheet/../tests/helpers/getters";
import {
    MOCK_SURVEY_DATA,
    createModelWithSurvey,
    defineDocumentSpreadsheetSurveyModels,
} from "./helpers";
const { cellMenuRegistry } = registries;

defineDocumentSpreadsheetSurveyModels();

test("ODOO.SURVEY formula results", async function () {
    const model = await createModelWithSurvey();

    expect(getCellValue(model, "A1")).toBe("Timestamp");
    expect(getCellValue(model, "A2")).toBe("2024-05-01 12:00:00");
    expect(getCellValue(model, "A3")).toBe("2024-05-02 12:00:00");
    expect(getCellValue(model, "B1")).toBe("How are you ?");
    expect(getCellValue(model, "B2")).toBe("Just fine !");
    expect(getCellValue(model, "B3")).toBe("Good");
    expect(getCellValue(model, "C1")).toBe("What's your age ?");
    expect(getCellValue(model, "C2")).toBe(25);
    expect(getCellValue(model, "C3")).toBe(35);
});

test("Can see record on survey formula header", async function () {
    const model = await createModelWithSurvey();
    setSelection(model, "A1");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "survey_see_record");
    const fakeActionService = {
        doAction: (actionRequest, options = {}) => {
            expect.step("doAction");
            expect(actionRequest.res_model).toBe("survey.survey");
            expect(actionRequest.res_id).toBe(1);
        },
    };

    const env = { model, services: { action: fakeActionService } };
    expect(root.isVisible(env)).toBe(true);
    expect(root.name(env)).toBe("See survey");
    await root.execute(env);
    expect.verifySteps(["doAction"]);
});

test("Can see record on survey formula content", async function () {
    const model = await createModelWithSurvey();
    setSelection(model, "A2");
    const root = cellMenuRegistry.getAll().find((item) => item.id === "survey_see_record");
    const fakeActionService = {
        doAction: (actionRequest, options = {}) => {
            expect.step("doAction");
            expect(actionRequest.res_model).toBe("survey.user_input");
            expect(actionRequest.res_id).toBe(MOCK_SURVEY_DATA.user_input_ids[0]);
        },
    };
    const env = { model, services: { action: fakeActionService } };
    expect(root.isVisible(env)).toBe(true);
    expect(root.name(env)).toBe("See survey participation");
    await root.execute(env);
    expect.verifySteps(["doAction"]);
});

test("See record is not present on wrong survey formulas", async function () {
    const model = await createModelWithSurvey();
    const root = cellMenuRegistry.getAll().find((item) => item.id === "survey_see_record");
    setCellContent(model, "A20", '=ODOO.SURVEY("NotASurveyId")'); // Invalid survey ID
    setSelection(model, "A20");
    const env = { model };
    expect(root.isVisible(env)).toBe(false);

    setCellContent(model, "A20", "=ODOO.SURVEY(25689)"); // Survey does not exist
    setSelection(model, "A20");
    expect(root.isVisible(env)).toBe(false);
});
