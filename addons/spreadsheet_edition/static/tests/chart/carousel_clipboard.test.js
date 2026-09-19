import { describe, expect, test } from "@odoo/hoot";
import { Model, helpers } from "@odoo/o-spreadsheet";
import {
    createSpreadsheetWithChart,
    insertChartInSpreadsheet,
} from "@spreadsheet/../tests/helpers/chart";
import {
    addGlobalFilter,
    createBasicChart,
    createCarousel,
    addChartFigureToCarousel,
} from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { makeSpreadsheetMockEnv } from "@spreadsheet/../tests/helpers/model";

describe.current.tags("headless");
defineSpreadsheetModels();

const { toZone } = helpers;

const serverData = {
    menus: {
        root: { id: "root", children: [1], name: "root", appID: "root" },
        1: {
            id: 1,
            children: [],
            name: "test menu 1",
            xmlid: "spreadsheet_edition.test.menu",
            appID: 1,
            actionID: "menuAction",
        },
    },
};

test("link is kept when copying charts inside of carousel", async () => {
    const env = await makeSpreadsheetMockEnv({ serverData });
    const model = new Model({}, { custom: { env } });

    createBasicChart(model, "chartId1", { type: "bar" }, undefined, "chartFigureId1");
    model.dispatch("LINK_ODOO_MENU_TO_CHART", { chartId: "chartId1", odooMenuId: 1 });
    createBasicChart(model, "chartId2", { type: "line" }, undefined, "chartFigureId2");
    model.dispatch("LINK_ODOO_MENU_TO_CHART", { chartId: "chartId2", odooMenuId: 1 });

    createCarousel(model, { items: [] }, "carouselId");
    addChartFigureToCarousel(model, "carouselId", "chartFigureId1");
    addChartFigureToCarousel(model, "carouselId", "chartFigureId2");

    expect(model.getters.getChartOdooMenu("chartId1").id).toBe(1);
    expect(model.getters.getChartOdooMenu("chartId2").id).toBe(1);

    const sheetId = model.getters.getActiveSheetId();
    model.dispatch("SELECT_FIGURE", { figureId: "carouselId" });
    model.dispatch("COPY");
    model.dispatch("PASTE", { target: [toZone("A1")] });

    const newCarouselId = model.getters.getFigures(sheetId)[1].id;
    const newCarousel = model.getters.getCarousel(newCarouselId);

    const newChartId1 = newCarousel.items[0].chartId;
    expect(model.getters.getChartOdooMenu(newChartId1).id).toBe(1);

    const newChartId2 = newCarousel.items[1].chartId;
    expect(model.getters.getChartOdooMenu(newChartId2).id).toBe(1);
});

test("cut/paste Odoo chart field matching inside carousels", async () => {
    const { model } = await createSpreadsheetWithChart({ type: "odoo_pie" });
    insertChartInSpreadsheet(model, "odoo_bar");
    const sheetId = model.getters.getActiveSheetId();
    const [chartFigureId1, chartFigureId2] = model.getters
        .getFigures(sheetId)
        .map((figure) => figure.id);
    const [chartId1, chartId2] = model.getters.getChartIds(sheetId);
    const fieldMatching = {
        chart: {
            [chartId1]: { type: "many2one", chain: "partner_id.company_id" },
            [chartId2]: { type: "many2one", chain: "user_id.company_id" },
        },
    };
    await addGlobalFilter(
        model,
        {
            id: "filterId",
            type: "relation",
            modelName: "res.company",
            label: "Relation Filter",
        },
        fieldMatching
    );

    createCarousel(model, { items: [] }, "carouselId");
    addChartFigureToCarousel(model, "carouselId", chartFigureId1);
    addChartFigureToCarousel(model, "carouselId", chartFigureId2);

    model.dispatch("SELECT_FIGURE", { figureId: "carouselId" });
    model.dispatch("CUT");
    model.dispatch("PASTE", { target: [toZone("A1")] });

    const chartIds = model.getters.getChartIds(sheetId);
    expect(model.getters.getOdooChartFieldMatching(chartIds[0], "filterId").chain).toBe(
        "partner_id.company_id"
    );
    expect(model.getters.getOdooChartFieldMatching(chartIds[1], "filterId").chain).toBe(
        "user_id.company_id"
    );
});
