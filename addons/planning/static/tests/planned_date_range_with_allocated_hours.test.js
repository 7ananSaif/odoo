import { expect, test, beforeEach } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";

import { mountView } from "@web/../tests/web_test_helpers";

import { definePlanningModels, planningModels } from "./planning_mock_models";

definePlanningModels();

beforeEach(() => {
    planningModels.PlanningSlot._records = [
        {
            display_name: "Planning Slot tester 1",
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        {
            display_name: "Planning Slot tester 2",
            allocated_hours: 10,
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
    ];
    mockDate("2023-11-09T08:00:00", 0);
});

test("planned_date_range_with_allocated_hours widget in list view", async () => {
    await mountView({
        resModel: "planning.slot",
        type: "list",
        arch: `<list>
            <field name="start_datetime" widget="planned_date_range_with_allocated_hours" options="{'end_date_field': 'end_datetime'}"/>
            <field name="end_datetime" invisible="1"/>
        </list>`,
    });

    expect(".o_list_view").toHaveCount(1);
    expect(".o_field_planned_date_range_with_allocated_hours").toHaveCount(2);
    expect(".o_field_planned_date_range_with_allocated_hours:first").toHaveText(
        "Nov 9, 12:00 AM\n10:00 PM"
    );
    expect(".o_field_planned_date_range_with_allocated_hours:last").toHaveText(
        "Nov 9, 12:00 AM\n10:00 PM\n(10:00)"
    );
});
