import { registry } from "@web/core/registry";
import { graphView } from "@web/views/graph/graph_view";
import { PlanningSlotAnalysisGraphRenderer } from "./planning_slot_analysis_graph_renderer";

registry.category("views").add("planning_slot_analysis_graph", {
    ...graphView,
    Renderer: PlanningSlotAnalysisGraphRenderer,
});
