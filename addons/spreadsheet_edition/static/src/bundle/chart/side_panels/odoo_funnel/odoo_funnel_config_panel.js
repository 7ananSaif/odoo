import { CommonOdooChartConfigPanel } from "../common/config_panel";
import { components } from "@odoo/o-spreadsheet";

const { Checkbox } = components;

export class OdooFunnelChartConfigPanel extends CommonOdooChartConfigPanel {
    static template = "spreadsheet_edition.OdooFunnelChartConfigPanel";
    static components = {
        ...CommonOdooChartConfigPanel.components,
        Checkbox,
    };

    onUpdateCumulative(cumulative) {
        this.props.updateChart(this.props.chartId, {
            cumulative,
        });
    }
}
