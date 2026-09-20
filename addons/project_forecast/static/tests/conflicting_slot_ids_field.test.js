import { expect, test } from "@odoo/hoot";
import { queryText } from "@odoo/hoot-dom";
import { mockTimeZone } from "@odoo/hoot-mock";

import { mountView } from "@web/../tests/web_test_helpers";
import { planningModels } from "@planning/../tests/planning_mock_models";
import { projectModels } from "@project/../tests/project_models";
import {
    PlanningSlot as ProjectForecastPlanningSlot,
    defineProjectForecastModels,
} from "./project_forecast_mock_models";

class PlanningSlot extends ProjectForecastPlanningSlot {
    _records = [
        {
            id: 1,
            conflicting_slot_ids: [2],
        },
        {
            id: 2,
            start_datetime: "2021-09-01 08:00:00",
            end_datetime: "2021-09-01 12:00:00",
            allocated_hours: 4,
            allocated_percentage: 100,
            project_id: 1,
        },
    ];

    _views = {
        form: `<form><field name="conflicting_slot_ids" widget="conflicting_slot_ids"/></form>`,
    };
}

class ProjectProject extends projectModels.ProjectProject {
    _records = [{ id: 1, name: "Project 1" }];
}

planningModels.PlanningSlot = PlanningSlot;
projectModels.ProjectProject = ProjectProject;

defineProjectForecastModels();

test("Test the conflict slot message content", async () => {
    mockTimeZone(+1);
    await mountView({
        resId: 1,
        resModel: "planning.slot",
        type: "form",
    });

    expect(".o_conflicting_slot").toHaveCount(1);
    expect(queryText(".o_conflicting_slot")).toBe(
        "Sep 1, 2021, 9:00 AMSep 1, 2021, 1:00 PM\n(4h) (100.00%) - Project 1"
    );
});
