import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { makeMockServer, mountView, onRpc } from "@web/../tests/web_test_helpers";
import { unfoldAllColumns } from "@web_gantt/../tests/web_gantt_test_helpers";

import { definePlanningModels } from "@planning/../tests/planning_mock_models";

definePlanningModels();

describe.current.tags("desktop");

let resourceId = false;
let versionId = false;
let env;

beforeEach(async () => {
    mockDate("2024-03-27");
    const mockServer = await makeMockServer();
    env = mockServer.env;
    const userId = env["res.users"].create({
        name: "Pig-1",
    });
    resourceId = env["resource.resource"].create({
        name: "Pig-1",
        user_id: userId,
        resource_type: "user",
    });

    env["planning.slot"].create({
        name: "Shift-1",
        state: "published",
        resource_id: resourceId,
        start_datetime: "2024-03-27 02:30:00",
        end_datetime: "2024-03-27 11:30:00",
    });

    const employeeId = env["hr.employee"].create({
        user_id: userId,
        name: "Pig-1",
        resource_id: resourceId,
    });
    versionId = env["hr.version"].create({
        name: "Contract - Pig",
        employee_id: employeeId,
        contract_date_start: "2024-03-28 00:00:00",
        contract_date_end: "2024-03-28 23:50:59",
    });
});

const ganttViewParams = {
    resModel: "planning.slot",
    type: "gantt",
    arch: `<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" default_group_by="resource_id"
                default_scale="week" display_unavailability="1" total_row="True">
           </gantt>`,
    context: {
        default_start_date: "2024-03-24",
        default_stop_date: "2024-03-30",
    },
};

onRpc("gantt_resource_work_interval", () => [
    {
        [resourceId]: [
            ["2024-03-25 09:00:00", "2024-03-25 18:00:00"],
            ["2024-03-25 09:00:00", "2024-03-25 18:00:00"],
            ["2024-03-26 09:00:00", "2024-03-26 18:00:00"],
            ["2024-03-26 09:00:00", "2024-03-26 18:00:00"],
            ["2024-03-27 09:00:00", "2024-03-27 18:00:00"],
            ["2024-03-27 09:00:00", "2024-03-27 18:00:00"],
            ["2024-03-28 09:00:00", "2024-03-28 18:00:00"],
            ["2024-03-28 09:00:00", "2024-03-28 18:00:00"],
            ["2024-03-29 09:00:00", "2024-03-29 18:00:00"],
            ["2024-03-29 09:00:00", "2024-03-29 18:00:00"],
        ],
        false: [
            ["2024-03-25 09:00:00", "2024-03-25 18:00:00"],
            ["2024-03-25 09:00:00", "2024-03-25 18:00:00"],
            ["2024-03-26 09:00:00", "2024-03-26 18:00:00"],
            ["2024-03-26 09:00:00", "2024-03-26 18:00:00"],
            ["2024-03-27 09:00:00", "2024-03-27 18:00:00"],
            ["2024-03-27 09:00:00", "2024-03-27 18:00:00"],
            ["2024-03-28 09:00:00", "2024-03-28 18:00:00"],
            ["2024-03-28 09:00:00", "2024-03-28 18:00:00"],
            ["2024-03-29 09:00:00", "2024-03-29 18:00:00"],
            ["2024-03-29 09:00:00", "2024-03-29 18:00:00"],
        ],
    },
    { false: 0, [resourceId]: 0 },
    { false: 0, [resourceId]: 9 },
]);

onRpc("get_gantt_data", function getGanttData({ parent, kwargs }) {
    const result = parent();
    result.unavailabilities = {
        resource_id: {
            [resourceId]: [
                { start: "2024-03-23 18:00:00", stop: "2024-03-25 09:00:00" },
                { start: "2024-03-28 18:00:00", stop: "2024-04-01 09:00:00" },
            ],
            false: [
                { start: "2024-03-23 18:00:00", stop: "2024-03-25 09:00:00" },
                { start: "2024-03-28 18:00:00", stop: "2024-04-01 09:00:00" },
            ],
        },
    };
    if (kwargs.groupby.includes("resource_id")) {
        result.working_periods = this.env["planning.slot"]._gantt_resource_employees_working_periods(result.groups, kwargs.start_date, kwargs.stop_date)
    }
    return result;
});

/*
    The following cases are to be checked/tested.
╔══════════╦══════════╦══════════════════╦══════════════════════════════════════════════════════╗
║ Employee ║ Contract ║ Status           ║ Behaviour                                            ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 1        ║ No       ║ None             ║ White it in working days and grey according          ║
║          ║          ║                  ║ to the employee calendar                             ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 2        ║ Yes      ║ Running          ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the employee calendar, and grey everywhere outside   ║
║          ║          ║                  ║ of the contract period                               ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 3        ║ Yes      ║ Expired          ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the employee calendar, and grey everywhere outside   ║
║          ║          ║                  ║ of the contract period                               ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 4        ║ Yes      ║ Cancelled        ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the employee calendar, and grey everywhere outside   ║
║          ║          ║                  ║ of the contract period                               ║
╚══════════╩══════════╩══════════════════╩══════════════════════════════════════════════════════╝
*/
test("check gantt shading for employee without contract (case-1)", async () => {
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']").toHaveCount(3);
    expect(".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff'])").toHaveCount(4);
});

test("check gantt shading for employee without contract (case-2)", async () => {
    env["hr.version"].write(versionId, {
        contract_date_start: "2024-03-27 00:00:00",
        contract_date_end: "2024-03-30 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_resource_has_no_working_periods").toHaveCount(3);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_resource_has_no_working_periods)"
    ).toHaveCount(2);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_resource_has_no_working_periods)"
    ).toHaveCount(2);
});

test("check gantt shading for employee without contract (case-3)", async () => {
    env["hr.version"].write(versionId, {
        contract_date_start: "2024-03-20 00:00:00",
        contract_date_end: "2024-03-25 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_resource_has_no_working_periods").toHaveCount(5);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_resource_has_no_working_periods)"
    ).toHaveCount(1);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_resource_has_no_working_periods)"
    ).toHaveCount(1);
});

test("check gantt shading for employee without contract (case-4)", async () => {
    env["hr.version"].write(versionId, {
        active: false,
        contract_date_start: "2024-03-27 00:00:00",
        contract_date_end: "2024-03-30 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_resource_has_no_working_periods").toHaveCount(0);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_resource_has_no_working_periods)"
    ).toHaveCount(3);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_resource_has_no_working_periods)"
    ).toHaveCount(4);
});
