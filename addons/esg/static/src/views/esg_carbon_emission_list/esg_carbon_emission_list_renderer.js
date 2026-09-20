import { ListRenderer } from "@web/views/list/list_renderer";

export class EsgCarbonEmissionListRenderer extends ListRenderer {
    get canCreate() {
        return false;
    }
}
