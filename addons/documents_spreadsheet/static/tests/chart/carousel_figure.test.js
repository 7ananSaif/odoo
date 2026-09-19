import { createSpreadsheetFromGraphView } from "@documents_spreadsheet/../tests/helpers/chart_helpers";
import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { createCarousel } from "@spreadsheet/../tests/helpers/commands";
import { contains } from "@web/../tests/web_test_helpers";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

test("Can add an odoo chart to a carousel figure", async () => {
    const { model } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    createCarousel(model, { items: [] }, "carouselId");
    await animationFrame();
    const fixture = getFixture();

    expect(model.getters.getFigures(sheetId)).toHaveLength(2);

    const [chartFigure, carouselFigure] = [...fixture.querySelectorAll(".o-figure")];
    await contains(chartFigure).dragAndDrop(carouselFigure, { position: "top" });

    expect(model.getters.getFigures(sheetId)).toHaveLength(1);
    expect(model.getters.getFigures(sheetId)[0].tag).toBe("carousel");
    expect(model.getters.getCarousel("carouselId").items).toEqual([
        { type: "chart", chartId: chartId },
    ]);
    expect(model.getters.getChartDefinition(chartId)).toMatchObject({ type: "odoo_bar" });
});

test("Link to menu id is preserved when adding a chart to a carousel", async () => {
    const { model } = await createSpreadsheetFromGraphView();
    createCarousel(model, { items: [] }, "carouselId");
    await animationFrame();
    const fixture = getFixture();

    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    model.dispatch("LINK_ODOO_MENU_TO_CHART", {
        chartId,
        odooMenuId: 1,
    });

    const [chartFigure, carouselFigure] = [...fixture.querySelectorAll(".o-figure")];
    await contains(chartFigure).dragAndDrop(carouselFigure, { position: "top" });

    expect(model.getters.getChartOdooMenu(chartId)?.id).toBe(1);
});
