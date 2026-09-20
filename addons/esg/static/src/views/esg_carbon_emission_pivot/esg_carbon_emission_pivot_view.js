import { registry } from "@web/core/registry";
import { pivotView } from "@web/views/pivot/pivot_view";
import { EsgCarbonEmissionPivotController } from "./esg_carbon_emission_pivot_controller";

export const EsgCarbonEmissionPivotView = {
    ...pivotView,
    Controller: EsgCarbonEmissionPivotController,
};

registry.category("views").add("esg_carbon_emission_pivot", EsgCarbonEmissionPivotView);
