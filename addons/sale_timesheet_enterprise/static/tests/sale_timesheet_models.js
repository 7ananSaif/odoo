import { defineModels } from "@web/../tests/web_test_helpers";

import { SaleOrderLine, ProductProduct } from "@sale_project/../tests/project_task_model";
import { defineTimesheetModels as defineTimesheetGridModels } from "@timesheet_grid/../tests/hr_timesheet_models";

export function defineTimesheetModels() {
    defineTimesheetGridModels();
    defineModels([SaleOrderLine, ProductProduct]);
}
