import { DashboardLoader } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_loader_service";
import { patch } from "@web/core/utils/patch";

patch(DashboardLoader.prototype, {
    _getFetchGroupsSpecification() {
        const spec = super._getFetchGroupsSpecification();
        spec.published_dashboard_ids.fields.is_from_data = {};
        return spec;
    },
});
