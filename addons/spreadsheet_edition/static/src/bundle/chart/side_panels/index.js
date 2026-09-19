import * as spreadsheet from "@odoo/o-spreadsheet";
import { CommonOdooChartConfigPanel } from "./common/config_panel";
import { OdooBarChartConfigPanel } from "./odoo_bar/odoo_bar_config_panel";
import { OdooLineChartConfigPanel } from "./odoo_line/odoo_line_config_panel";
import { OdooGeoChartConfigPanel } from "./odoo_geo/odoo_geo_config_panel";
import { OdooFunnelChartConfigPanel } from "./odoo_funnel/odoo_funnel_config_panel";

const { chartSidePanelComponentRegistry } = spreadsheet.registries;
const {
    ComboChartDesignPanel,
    PieChartDesignPanel,
    ChartWithAxisDesignPanel,
    LineChartDesignPanel,
    RadarChartDesignPanel,
    WaterfallChartDesignPanel,
    GeoChartDesignPanel,
    FunnelChartDesignPanel,
    SunburstChartDesignPanel,
    TreeMapChartDesignPanel,
    GenericZoomableChartDesignPanel,
} = spreadsheet.components;

chartSidePanelComponentRegistry
    .add("odoo_line", {
        configuration: OdooLineChartConfigPanel,
        design: LineChartDesignPanel,
    })
    .add("odoo_bar", {
        configuration: OdooBarChartConfigPanel,
        design: GenericZoomableChartDesignPanel,
    })
    .add("odoo_pie", {
        configuration: CommonOdooChartConfigPanel,
        design: PieChartDesignPanel,
    })
    .add("odoo_radar", {
        configuration: CommonOdooChartConfigPanel,
        design: RadarChartDesignPanel,
    })
    .add("odoo_sunburst", {
        configuration: CommonOdooChartConfigPanel,
        design: SunburstChartDesignPanel,
    })
    .add("odoo_treemap", {
        configuration: CommonOdooChartConfigPanel,
        design: TreeMapChartDesignPanel,
    })
    .add("odoo_waterfall", {
        configuration: CommonOdooChartConfigPanel,
        design: WaterfallChartDesignPanel,
    })
    .add("odoo_pyramid", {
        configuration: CommonOdooChartConfigPanel,
        design: ChartWithAxisDesignPanel,
    })
    .add("odoo_scatter", {
        configuration: CommonOdooChartConfigPanel,
        design: GenericZoomableChartDesignPanel,
    })
    .add("odoo_combo", {
        configuration: CommonOdooChartConfigPanel,
        design: ComboChartDesignPanel,
    })
    .add("odoo_geo", {
        configuration: OdooGeoChartConfigPanel,
        design: GeoChartDesignPanel,
    })
    .add("odoo_funnel", {
        configuration: OdooFunnelChartConfigPanel,
        design: FunnelChartDesignPanel,
    });
