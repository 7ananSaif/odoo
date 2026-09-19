import {
    createSpreadsheetFromGraphView,
    openChartSidePanel,
} from "@documents_spreadsheet/../tests/helpers/chart_helpers";
import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { createSpreadsheet } from "@documents_spreadsheet/../tests/helpers/spreadsheet_test_utils";
import { describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { registries } from "@odoo/o-spreadsheet";
import { addGlobalFilter, createBasicChart } from "@spreadsheet/../tests/helpers/commands";
import * as dsHelpers from "@web/../tests/core/tree_editor/condition_tree_editor_test_helpers";
import { contains, makeServerError, onRpc, fields } from "@web/../tests/web_test_helpers";
import { Partner } from "@spreadsheet/../tests/helpers/data";

defineDocumentSpreadsheetModels();
describe.current.tags("desktop");

const { chartSubtypeRegistry } = registries;

async function changeChartType(type) {
    await contains(".o-type-selector").click();
    await contains(`.o-chart-type-item[data-id="${type}"]`).click();
}

test("Open a chart panel", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    await openChartSidePanel(model, env);
    expect(".o-sidePanel .o-sidePanelBody .o-chart").toHaveCount(1);
});

test("From an Odoo chart, can only change to an Odoo chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    await openChartSidePanel(model, env);
    const target = getFixture();
    await contains(".o-type-selector").click();
    const odooChartTypes = chartSubtypeRegistry
        .getKeys()
        .filter((key) => key.startsWith("odoo_") && key !== "odoo_geo")
        .sort();
    /** @type {NodeListOf<HTMLDivElement>} */
    const options = target.querySelectorAll(".o-chart-type-item");
    const optionValues = Array.from(options)
        .map((option) => option.dataset.id)
        .sort();
    expect(optionValues).toEqual(odooChartTypes);
});

test("From a spreadsheet chart, can only change to a spreadsheet chart", async () => {
    const { model, env } = await createSpreadsheet();
    createBasicChart(model, "1");
    await openChartSidePanel(model, env);
    const target = getFixture();
    await contains(".o-type-selector").click();
    /** @type {NodeListOf<HTMLDivElement>} */
    const options = target.querySelectorAll(".o-chart-type-item");
    const optionValues = Array.from(options)
        .map((option) => option.dataset.id)
        .sort();
    const nonOdooChartTypes = chartSubtypeRegistry
        .getKeys()
        .filter((key) => !key.startsWith("odoo_"))
        .sort();

    expect(optionValues).toEqual(nonOdooChartTypes);
});

test("Possible chart types are correct when switching from a spreadsheet to an odoo chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    createBasicChart(model, "nonOdooChartId", {}, undefined, "figureId");
    await openChartSidePanel(model, env);
    const target = getFixture();
    await contains(".o-type-selector").click();

    /** @type {NodeListOf<HTMLDivElement>} */
    let options = target.querySelectorAll(".o-chart-type-item");
    let optionValues = Array.from(options).map((option) => option.dataset.id);
    expect(optionValues.every((value) => value.startsWith("odoo_"))).toBe(true);

    model.dispatch("SELECT_FIGURE", { figureId: "figureId" });
    await animationFrame();

    await contains(".o-type-selector").click();
    options = target.querySelectorAll(".o-chart-type-item");
    optionValues = Array.from(options).map((option) => option.dataset.id);
    expect(optionValues.every((value) => !value.startsWith("odoo_"))).toBe(true);
});

test("Change odoo chart type", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    expect(model.getters.getChart(chartId).type).toBe("odoo_bar");
    await openChartSidePanel(model, env);
    /** @type {HTMLSelectElement} */
    await changeChartType("odoo_pie");
    expect(model.getters.getChart(chartId).type).toBe("odoo_pie");

    await changeChartType("odoo_line");
    expect(model.getters.getChart(chartId).verticalAxisPosition).toBe("left");
    expect(model.getters.getChart(chartId).stacked).toBe(false);

    await changeChartType("odoo_bar");
    expect(model.getters.getChart(chartId).type).toBe("odoo_bar");
    expect(model.getters.getChart(chartId).stacked).toBe(false);

    await changeChartType("odoo_stacked_bar");
    expect(model.getters.getChart(chartId).type).toBe("odoo_bar");
    expect(model.getters.getChart(chartId).stacked).toBe(true);

    await changeChartType("odoo_stacked_line");
    expect(model.getters.getChart(chartId).type).toBe("odoo_line");
    expect(model.getters.getChart(chartId).stacked).toBe(true);
});

test("data markers are displayed by default for line, combo and radar charts", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    expect(model.getters.getChart(chartId).type).toBe("odoo_bar");
    await openChartSidePanel(model, env);

    await changeChartType("odoo_line");
    expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(undefined);

    await changeChartType("odoo_combo");
    expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(undefined);

    await changeChartType("odoo_radar");
    expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(undefined);
});

for (const type of ["odoo_line", "odoo_combo", "odoo_radar"]) {
    test(`can toggle data markers for ${type}`, async () => {
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await changeChartType(type);
        await contains(".o-panel-design").click();
        expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(undefined);
        await contains(".o-checkbox input[name='showDataMarkers']:checked").click();
        expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(true);
        await contains(".o-checkbox input[name='showDataMarkers']").click();
        expect(model.getters.getChartDefinition(chartId).hideDataMarkers).toBe(false);
    });
}

test("stacked line chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_stacked_line");

    // checked by default
    expect(model.getters.getChart(chartId).stacked).toBe(true);
    expect(".o-checkbox input[name='stackedBar']:checked").toHaveCount(1, {
        message: "checkbox should be checked",
    });

    // uncheck
    await contains(".o-checkbox input:checked").click();
    expect(model.getters.getChart(chartId).stacked).toBe(false);
    expect(".o-checkbox input[name='stackedBar']:checked").toHaveCount(0, {
        message: "checkbox should no longer be checked",
    });

    // check
    await contains(".o-checkbox input[name='stackedBar']").click();
    expect(model.getters.getChart(chartId).stacked).toBe(true);
    expect(".o-checkbox input[name='stackedBar']:checked").toHaveCount(1, {
        message: "checkbox should be checked",
    });
});

test("Odoo line chart with cumulated start", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_line");

    expect(model.getters.getChartDefinition(chartId).cumulative).toBe(undefined);
    expect(model.getters.getChartDefinition(chartId).cumulatedStart).toBe(undefined);
    expect(".o-checkbox input[name='cumulatedStart']").toHaveCount(0, {
        message: "cumulated Start is not visible",
    });

    // uncheck
    await contains(".o-checkbox input[name='cumulative']").click();
    expect(model.getters.getChart(chartId).cumulative).toBe(true);
    expect(model.getters.getChart(chartId).cumulatedStart).toBe(undefined);
    expect(".o-checkbox input[name='cumulatedStart']").toHaveCount(1, {
        message: "cumulated Start is visible",
    });
    expect(".o-checkbox input[name='cumulatedStart']:checked").toHaveCount(0, {
        message: "cumulated Start not checked",
    });

    // check
    await contains(".o-checkbox input[name='cumulatedStart']").click();
    expect(model.getters.getChart(chartId).cumulative).toBe(true);
    expect(model.getters.getChart(chartId).cumulatedStart).toBe(true);
    expect(".o-checkbox input[name='cumulatedStart']:checked").toHaveCount(1, {
        message: "cumulated Start is visible and checked",
    });
});

test("Odoo area chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_area");

    let chartDefinition = model.getters.getChartDefinition(chartId);
    expect(chartDefinition.type).toBe("odoo_line");
    expect(chartDefinition.fillArea).toBe(true);
    expect(chartDefinition.stacked).toBe(false);

    await changeChartType("odoo_stacked_area");
    chartDefinition = model.getters.getChartDefinition(chartId);
    expect(chartDefinition.type).toBe("odoo_line");
    expect(chartDefinition.fillArea).toBe(true);
    expect(chartDefinition.stacked).toBe(true);
});

test("Change the title of a chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    expect(model.getters.getChart(chartId).type).toBe("odoo_bar");
    await openChartSidePanel(model, env);
    const target = getFixture();
    await contains(".o-panel-design").click();
    /** @type {HTMLInputElement} */
    const input = target.querySelector(".o-chart-title input");
    expect(model.getters.getChart(chartId).title.text).toBe("PartnerGraph");
    await contains(input).edit("bla");
    expect(model.getters.getChart(chartId).title.text).toBe("bla");
});

test("Open chart odoo's data properties", async function () {
    const target = getFixture();
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const figureId = model.getters.getFigures(sheetId)[0].id;

    // opening from a chart
    model.dispatch("SELECT_FIGURE", { figureId });
    env.openSidePanel("ChartPanel");
    await animationFrame();

    const sections = target.querySelectorAll(".o-panel-content > div:not(.d-none) .o-section");
    expect(sections.length).toBe(6, { message: "it should have 6 sections" });
    const [, , pivotModel, domain, , measures] = sections;

    expect(pivotModel.children[0]).toHaveText("Model");
    expect(pivotModel.children[1]).toHaveText("Partner (partner)");

    expect(domain.children[0]).toHaveText("Domain");
    expect(domain.children[1]).toHaveText("Match all records\nInclude archived");

    expect(measures.children[0].innerText.startsWith("Last updated at")).toBe(true);
});

test("Update the chart domain from the side panel", async function () {
    onRpc("/web/domain/validate", () => true);
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    const figureId = model.getters.getFigures(sheetId)[0].id;
    model.dispatch("SELECT_FIGURE", { figureId });
    env.openSidePanel("ChartPanel");
    await animationFrame();
    const fixture = getFixture();
    await contains(".o_edit_domain").click();
    await dsHelpers.addNewRule();
    await contains(".modal-footer .btn-primary").click();
    expect(model.getters.getChartDefinition(chartId).searchParams.domain).toEqual([["id", "=", 1]]);
    expect(dsHelpers.getConditionText(fixture)).toBe("Id = 1");
});

test("Cumulative line chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_line");
    await contains(".o-checkbox input[name='cumulative']").click();
    // check
    expect(model.getters.getChart(chartId).cumulative).toBe(true);
    expect(".o-checkbox input[name='cumulative']:checked").toHaveCount(1, {
        message: "checkbox should be checked",
    });

    // uncheck
    await contains(".o-checkbox input[name='cumulative']").click();
    expect(model.getters.getChart(chartId).cumulative).toBe(false);
    expect(".o-checkbox input[name='cumulative']:checked").toHaveCount(0, {
        message: "checkbox should no longer be checked",
    });
});

test("radar chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_radar");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_radar");
    expect(model.getters.getChartRuntime(chartId).chartJsConfig.type).toBe("radar");
});

test("filled radar chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_filled_radar");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_radar");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("radar");
    expect(runtime.chartJsConfig.data.datasets[0].fill).toBe("start");
});

test("waterfall chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_waterfall");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_waterfall");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("bar");
    expect(runtime.chartJsConfig.options.plugins.waterfallLinesPlugin).toEqual({
        showConnectorLines: true,
    });
});

test("population pyramid chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView({
        additionalContext: {
            graph_groupbys: ["bar", "product_id"],
            graph_measure: ["probability"],
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_pyramid");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_pyramid");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("bar");
    expect(runtime.chartJsConfig.data.datasets[0].data).toEqual([15, 106]);
    // negative values for the other side of the pyramid
    expect(runtime.chartJsConfig.data.datasets[1].data).toEqual([0, -10]);
});

test("scatter chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_scatter");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_scatter");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("line");
    expect(runtime.chartJsConfig.data.datasets[0].showLine).toBe(false);
});

test("geo chart", async () => {
    const country_id = fields.Many2one({ string: "Country", relation: "res.country" });
    Partner._fields = { ...Partner._fields, country_id };

    const mockGeoJson = {
        type: "FeatureCollection",
        features: [{ type: "Feature", id: "BE", properties: { name: "Belgium" }, geometry: {} }],
    };
    onRpc("/spreadsheet/static/topojson/world.topo.json", () => mockGeoJson);
    onRpc("/spreadsheet/static/topojson/europe.topo.json", () => mockGeoJson);

    const { model, env } = await createSpreadsheetFromGraphView({
        additionalContext: {
            graph_groupbys: ["country_id"],
            graph_measure: ["probability"],
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_geo");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_geo");
    expect(model.getters.getChartRuntime(chartId).chartJsConfig.type).toBe("choropleth");

    await contains(".o-geo-region select").select("europe");
    expect(model.getters.getChartDefinition(chartId).region).toBe("europe");
});

test("sunburst chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView({
        additionalContext: {
            graph_groupbys: ["product_id", "date:month"],
            graph_measure: ["probability"],
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_sunburst");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_sunburst");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("doughnut");
    expect(runtime.chartJsConfig.options.plugins.sunburstHoverPlugin).toEqual({ enabled: true });
    expect(runtime.chartJsConfig.data.datasets[0].data).toMatchObject([
        { groups: ["xpad", "December 2016"], label: "December 2016", value: 110 },
        { groups: ["xpad", "October 2016"], label: "October 2016", value: 11 },
        { groups: ["xphone", "April 2016"], label: "April 2016", value: 10 },
    ]);
    expect(runtime.chartJsConfig.data.datasets[1].data).toMatchObject([
        { groups: ["xpad"], label: "xpad", value: 121 },
        { groups: ["xphone"], label: "xphone", value: 10 },
    ]);
});

test("treemap chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView({
        additionalContext: {
            graph_groupbys: ["product_id", "date:month"],
            graph_measure: ["probability"],
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_treemap");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_treemap");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("treemap");
    expect(runtime.chartJsConfig.data.datasets[0].tree).toEqual([
        { 0: "xphone", 1: "April 2016", value: 10 },
        { 0: "xpad", 1: "October 2016", value: 11 },
        { 0: "xpad", 1: "December 2016", value: 110 },
    ]);
});

test("cannot change chart type to geo chart for a chart not grouped by country", async () => {
    const { model, env } = await createSpreadsheetFromGraphView({});
    await openChartSidePanel(model, env);
    await contains(".o-type-selector").click();
    expect(".o-chart-type-item[data-id='odoo_geo']").toHaveCount(0);
});

test("combo chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView({
        additionalContext: {
            graph_groupbys: ["bar", "product_id"],
            graph_measure: ["probability"],
        },
    });
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_combo");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_combo");
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("bar");
    expect(runtime.chartJsConfig.data.datasets[0].type).toBe("bar");
    expect(runtime.chartJsConfig.data.datasets[1].type).toBe("line");
});

test("horizontal & stacked horizontal bar charts", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_horizontal_bar");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_bar");
    let runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("bar");
    expect(runtime.chartJsConfig.options.indexAxis).toBe("y");
    expect(runtime.chartJsConfig.options.scales.x.stacked).toBe(false);

    await changeChartType("odoo_horizontal_stacked_bar");
    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_bar");
    runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("bar");
    expect(runtime.chartJsConfig.options.indexAxis).toBe("y");
    expect(runtime.chartJsConfig.options.scales.x.stacked).toBe(true);
});

test("doughnut charts", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_doughnut");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_pie");
    expect(model.getters.getChartDefinition(chartId).isDoughnut).toBe(true);
    const runtime = model.getters.getChartRuntime(chartId);
    expect(runtime.chartJsConfig.type).toBe("doughnut");
});

test("funnel chart", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await changeChartType("odoo_funnel");

    expect(model.getters.getChartDefinition(chartId).type).toBe("odoo_funnel");
    expect(model.getters.getChartDefinition(chartId).cumulative).toBe(true);
    expect(model.getters.getChartRuntime(chartId).chartJsConfig.type).toBe("funnel");
});

describe("trend line", () => {
    test("activate trend line with the checkbox", async function () {
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await contains(".o-panel-design").click();

        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();

        await contains("input[name='showTrendLine']").click();
        const definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend).toEqual({
            type: "polynomial",
            order: 1,
            display: true,
        });
        const runtime = model.getters.getChartRuntime(chartId);
        expect(runtime.chartJsConfig.data.datasets.length).toBe(2);
    });

    test("Axistype for odoo line chart trendlines must be defined", async function () {
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await changeChartType("odoo_line");
        await contains(".o-panel-design").click();
        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();
        await contains("input[name='showTrendLine']").click();
        const runtime = model.getters.getChartRuntime(chartId);
        expect(runtime.chartJsConfig.options.scales.x1.type).toBe("category");
    });

    test("Can change trend type", async function () {
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await contains(".o-panel-design").click();

        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();

        await contains("input[name='showTrendLine']").click();
        let definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend).toEqual({
            type: "polynomial",
            order: 1,
            display: true,
        });

        await contains(".trend-type-selector").select("logarithmic");
        definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend?.type).toBe("logarithmic");
    });

    test("Can change polynomial degree", async function () {
        onRpc("formatted_read_group", () =>
            // return at least 3 groups to have a valid trend line
            [
                {
                    bar: true,
                    __count: 1,
                    __domain: [],
                },
                {
                    bar: false,
                    __count: 2,
                    __domain: [],
                },
                {
                    bar: null,
                    __count: 3,
                    __domain: [],
                },
            ]
        );
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await contains(".o-panel-design").click();

        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();

        await contains("input[name='showTrendLine']").click();
        let definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend).toEqual({
            type: "polynomial",
            order: 1,
            display: true,
        });

        await contains(".trend-type-selector").select("polynomial");
        definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend).toEqual({
            type: "polynomial",
            order: 2,
            display: true,
        });

        await contains(".trend-order-input").select("1");
        definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets[0].trend?.order).toBe(1);
    });
});

test("Show values", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await contains(".o-panel-design").click();

    const collapsible = document.querySelectorAll(".collapsor");
    await collapsible[1].click();

    expect(model.getters.getChartDefinition(chartId).showValues).toBe(undefined);
    let options = model.getters.getChartRuntime(chartId).chartJsConfig.options;
    expect(options.plugins.chartShowValuesPlugin.showValues).toBe(false);

    await contains("input[name='showValues']").click();

    expect(model.getters.getChartDefinition(chartId).showValues).toBe(true);
    options = model.getters.getChartRuntime(chartId).chartJsConfig.options;
    expect(options.plugins.chartShowValuesPlugin.showValues).toBe(true);
});

test("Use compact format (humanize numbers)", async () => {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await openChartSidePanel(model, env);
    await contains(".o-panel-design").click();

    expect(model.getters.getChartDefinition(chartId).humanize).toBe(true);
    let options = model.getters.getChartRuntime(chartId).chartJsConfig.options;
    expect(options.scales.y.ticks.callback(100000)).toBe("100k");

    await contains("input[name='humanizeNumbers']").click();

    expect(model.getters.getChartDefinition(chartId).humanize).toBe(false);
    options = model.getters.getChartRuntime(chartId).chartJsConfig.options;
    expect(options.scales.y.ticks.callback(100000)).toBe("100,000");
});

describe("Can edit chart data series", () => {
    test("Can edit bar chart data series ", async function () {
        const { model, env } = await createSpreadsheetFromGraphView();
        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await contains(".o-panel-design").click();

        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();

        await contains(".o-radio input[value='right']").click();
        await contains(".o-serie-label-editor").edit("Random name");
        const definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets).toEqual([
            {
                label: "Random name",
                yAxisId: "y1",
            },
        ]);
    });

    test("Can edit line chart data series ", async function () {
        const { model, env } = await createSpreadsheetFromGraphView();
        await changeChartType("odoo_line");

        const sheetId = model.getters.getActiveSheetId();
        const chartId = model.getters.getChartIds(sheetId)[0];
        await openChartSidePanel(model, env);
        await contains(".o-panel-design").click();

        const collapsible = document.querySelectorAll(".collapsor");
        await collapsible[1].click();

        await contains(".o-radio input[value='right']").click();
        await contains(".o-serie-label-editor").edit("Random name");
        const definition = model.getters.getChartDefinition(chartId);
        expect(definition.dataSets).toEqual([
            {
                label: "Random name",
                yAxisId: "y1",
            },
        ]);
    });
});

test("An error is displayed in the side panel if the chart has invalid model", async function () {
    const { model, env } = await createSpreadsheetFromGraphView({
        mockRPC: async function (route, { model, method, kwargs }) {
            if (method === "fields_get") {
                throw makeServerError({ code: 404 });
            }
        },
    });
    await openChartSidePanel(model, env);

    expect(".o-validation-error").toHaveCount(1);
});

test("display chart related filters", async function () {
    const { model, env } = await createSpreadsheetFromGraphView();
    const sheetId = model.getters.getActiveSheetId();
    const chartId = model.getters.getChartIds(sheetId)[0];
    await addGlobalFilter(
        model,
        { id: "42", type: "relation", label: "Filter" },
        {
            chart: {
                [chartId]: {
                    chain: "product_id",
                    type: "many2one",
                },
            },
        }
    );
    await addGlobalFilter(model, { id: "43", type: "relation", label: "Filter 2" });
    await openChartSidePanel(model, env);
    expect(".o_side_panel_collapsible_title:contains(Matching 1 / 2 filters)").toHaveCount(1);
});
