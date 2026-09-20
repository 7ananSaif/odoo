import { CommonOdooChartConfigPanel } from "../common/config_panel";
import { components } from "@odoo/o-spreadsheet";

const { GeoChartRegionSelectSection } = components;

export class OdooGeoChartConfigPanel extends CommonOdooChartConfigPanel {
    static template = "spreadsheet_edition.OdooGeoChartConfigPanel";
    static components = {
        ...CommonOdooChartConfigPanel.components,
        GeoChartRegionSelectSection,
    };
}
