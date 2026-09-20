import { registry } from "@web/core/registry";
import { graphView } from "@web/views/graph/graph_view";
import { EsgCarbonEmissionGraphController } from "./esg_carbon_emission_graph_controller";

export const EsgCarbonEmissionGraphView = {
    ...graphView,
    Controller: EsgCarbonEmissionGraphController,
};

registry.category("views").add("esg_carbon_emission_graph", EsgCarbonEmissionGraphView);
