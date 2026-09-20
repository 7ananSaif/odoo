import { patch } from "@web/core/utils/patch";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { onWillUpdateProps } from "@odoo/owl";

const { chartSubtypeRegistry } = spreadsheet.registries;
const { ChartTypePicker } = spreadsheet.components;

const GEO_RES_MODELS = ["res.country", "res.country.state"];

/**
 * This patch is necessary to ensure that the chart type cannot be changed
 * between odoo charts and spreadsheet charts.
 */

patch(ChartTypePicker.prototype, {
    setup() {
        super.setup();
        this.updateChartTypeByCategories(this.props);
        onWillUpdateProps((nexProps) => this.updateChartTypeByCategories(nexProps));
    },

    onTypeChange(type) {
        if (this.getChartDefinition(this.props.chartId).type.startsWith("odoo_")) {
            const newChartInfo = chartSubtypeRegistry.get(type);
            const definition = {
                verticalAxisPosition: "left",
                ...this.env.model.getters.getChartDefinition(this.props.chartId),
                ...newChartInfo.subtypeDefinition,
                type: newChartInfo.chartType,
            };
            this.env.model.dispatch("UPDATE_CHART", {
                definition,
                chartId: this.props.chartId,
                figureId: this.env.model.getters.getFigureIdFromChartId(this.props.chartId),
                sheetId: this.env.model.getters.getActiveSheetId(),
            });
            this.closePopover();
        } else {
            super.onTypeChange(type);
        }
    },
    updateChartTypeByCategories(props) {
        const definition = this.env.model.getters.getChartDefinition(props.chartId);
        const isOdoo = definition.type.startsWith("odoo_");
        const registryItems = chartSubtypeRegistry.getAll().filter((item) => {
            if (isOdoo && item.chartType === "odoo_geo") {
                return this.isGeoChartTypeAvailable(props.chartId);
            }
            return isOdoo
                ? item.chartType.startsWith("odoo_")
                : !item.chartType.startsWith("odoo_");
        });

        this.chartTypeByCategories = {};
        for (const chartInfo of registryItems) {
            if (this.chartTypeByCategories[chartInfo.category]) {
                this.chartTypeByCategories[chartInfo.category].push(chartInfo);
            } else {
                this.chartTypeByCategories[chartInfo.category] = [chartInfo];
            }
        }
    },
    isGeoChartTypeAvailable(chartId) {
        const chart = this.env.model.getters.getChart(chartId);
        const groupBy = chart.getDefinition().metaData.groupBy;
        if (!groupBy || groupBy.length !== 1 || !chart.dataSource.isValid()) {
            return false;
        }
        const field = chart.dataSource.getField(groupBy[0]);
        return field && field.type === "many2one" && GEO_RES_MODELS.includes(field.relation);
    },
});
