import { registry } from "@web/core/registry";
import { pivotView } from "@web/views/pivot/pivot_view";
import { PlanningSlotAnalysisPivotRenderer } from "./planning_slot_analysis_pivot_renderer";

registry.category("views").add("planning_slot_analysis_pivot", {
    ...pivotView,
    Renderer: PlanningSlotAnalysisPivotRenderer,
});
