import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "../helpers/spreadsheet_test_utils";
import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { onRpc } from "@web/../tests/web_test_helpers";
import { runAllTimers } from "@odoo/hoot-mock";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

const mockWorldTopoJson = {
    type: "FeatureCollection",
    features: [
        { type: "Feature", id: "FR", properties: { name: "France" }, geometry: {} },
        { type: "Feature", id: "BE", properties: { name: "Belgium" }, geometry: {} },
        { type: "Feature", id: "US", properties: { name: "United States" }, geometry: {} },
    ],
};

const mockUSStatesTopoJson = {
    type: "FeatureCollection",
    features: [
        { type: "Feature", id: "CA", properties: { name: "California" }, geometry: {} },
        { type: "Feature", id: "TX", properties: { name: "Texas" }, geometry: {} },
        { type: "Feature", id: "NY", properties: { name: "New York" }, geometry: {} },
    ],
};

function getGeoChartRuntimeData(runtime) {
    return runtime.data.datasets[0].data.map((d) => ({
        value: d.value,
        id: d.feature.id,
    }));
}

beforeEach(async () => {
    onRpc("/spreadsheet/static/topojson/world.topo.json", () => mockWorldTopoJson);
    onRpc("/spreadsheet/static/topojson/usa.topo.json", () => mockUSStatesTopoJson);
});

test("The geoJson service is given to the model for geo charts", async function () {
    const { model } = await createSpreadsheet();

    expect(model.getters.getGeoChartAvailableRegions().map((r) => r.label)).toEqual([
        "World",
        "Africa",
        "Asia",
        "Europe",
        "North America",
        "United States",
        "South America",
    ]);

    expect(model.getters.getGeoJsonFeatures("world")).toEqual(undefined);
    await runAllTimers();
    expect(model.getters.getGeoJsonFeatures("world")).toEqual(mockWorldTopoJson.features);
    expect(model.getters.geoFeatureNameToId("world", "Belgium")).toEqual("BE");
});

test("Can create a geo chart on countries", async function () {
    const { model } = await createSpreadsheet();
    setCellContent(model, "A2", "United States");
    setCellContent(model, "B2", "25");
    setCellContent(model, "A3", "Belgium");
    setCellContent(model, "B3", "50");

    const sheetId = model.getters.getActiveSheetId();
    model.dispatch("CREATE_CHART", {
        chartId: "chartId",
        figureId: "figureId",
        sheetId,
        col: 0,
        row: 0,
        offset: { x: 0, y: 0 },
        definition: {
            type: "geo",
            title: { text: "test" },
            legendPosition: "none",
            dataSets: [{ dataRange: "B1:B3" }],
            labelRange: "A1:A3",
            dataSetsHaveTitle: false,
            region: "world",
        },
    });
    let runtime = model.getters.getChartRuntime("chartId").chartJsConfig;
    expect(runtime.type).toBe("choropleth");
    expect(getGeoChartRuntimeData(runtime)).toEqual([]);
    await runAllTimers();

    runtime = model.getters.getChartRuntime("chartId").chartJsConfig;
    expect(getGeoChartRuntimeData(runtime)).toEqual([
        { value: undefined, id: "FR" },
        { value: 50, id: "BE" },
        { value: 25, id: "US" },
    ]);
});

test("Can create a geo chart on US states", async function () {
    // Ideally we'd want to rely on the records in the mockServer, but the mocked searchRead don't seems to work
    // with domain [["country_id.code", "=", "US"]] ...
    onRpc("res.country.state", "search_read", () => [
        { name: "California", code: "CA" },
        { name: "Texas", code: "TX" },
        { name: "New York", code: "NY" },
    ]);
    const { model } = await createSpreadsheet();
    setCellContent(model, "A2", "California");
    setCellContent(model, "B2", "25");
    setCellContent(model, "A3", "Texas (US)"); // display_name of res.country.state is postfixed with country code
    setCellContent(model, "B3", "50");

    const sheetId = model.getters.getActiveSheetId();
    model.dispatch("CREATE_CHART", {
        chartId: "chartId",
        figureId: "figureId",
        sheetId,
        col: 0,
        row: 0,
        offset: { x: 0, y: 0 },
        definition: {
            type: "geo",
            region: "usa",
            title: { text: "test" },
            legendPosition: "none",
            dataSets: [{ dataRange: "B1:B3" }],
            labelRange: "A1:A3",
            dataSetsHaveTitle: false,
        },
    });
    await runAllTimers();

    const runtime = model.getters.getChartRuntime("chartId").chartJsConfig;
    expect(runtime.type).toBe("choropleth");
    expect(getGeoChartRuntimeData(runtime)).toEqual([
        { value: 25, id: "CA" },
        { value: 50, id: "TX" },
        { value: undefined, id: "NY" },
    ]);
});
