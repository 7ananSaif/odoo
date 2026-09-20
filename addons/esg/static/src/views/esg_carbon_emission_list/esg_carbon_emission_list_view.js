import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { EsgCarbonEmissionListController } from "./esg_carbon_emission_list_controller";
import { EsgCarbonEmissionListRenderer } from "./esg_carbon_emission_list_renderer";

export const EsgCarbonEmissionListView = {
    ...listView,
    Controller: EsgCarbonEmissionListController,
    Renderer: EsgCarbonEmissionListRenderer,
};

registry.category("views").add("esg_carbon_emission_list", EsgCarbonEmissionListView);
