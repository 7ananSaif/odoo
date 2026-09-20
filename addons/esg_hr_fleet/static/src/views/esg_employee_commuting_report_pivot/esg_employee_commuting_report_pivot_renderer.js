import { useService } from "@web/core/utils/hooks";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";

export class EsgEmployeeCommutingReportPivotRenderer extends PivotRenderer {
    setup() {
        super.setup(...arguments);
        this.action = useService("action");
    }

    onAddEmissionsClicked() {
        this.action.doAction("esg_hr_fleet.employee_commuting_emissions_wizard_action");
    }
}
