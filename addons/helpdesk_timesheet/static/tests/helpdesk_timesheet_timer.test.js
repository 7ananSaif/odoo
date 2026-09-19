import { beforeEach, describe, test, expect } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mountView, onRpc, contains } from "@web/../tests/web_test_helpers";
import { patchSession, hrTimesheetModels } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineHelpdeskTimesheetModels } from "./helpdesk_timesheet_models";
import { helpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";

describe.current.tags("desktop");
defineHelpdeskTimesheetModels();

beforeEach(() => {
    patchSession();
    hrTimesheetModels.HRTimesheet._views.grid = hrTimesheetModels.HRTimesheet._views.grid
        .replace("timesheet_grid", "timer_timesheet_grid")
        .replace('widget="float_time"', 'widget="timesheet_uom"');
    hrTimesheetModels.HRTimesheet._views["grid,1"] = hrTimesheetModels.HRTimesheet._views["grid,1"]
        .replace("timesheet_grid", "timer_timesheet_grid")
        .replace('widget="float_time"', 'widget="timesheet_uom"');

    helpdeskModels.HelpdeskTeam._records.push({
        id: 3,
        project_id: 1,
        name: "Team 3",
    });

    helpdeskModels.HelpdeskTicket._records.push({
        id: 4,
        project_id: 1,
        name: "Ticket 4",
    });

    hrTimesheetModels.HRTimesheet._records.push({
        id: 10,
        unit_amount: 5740 / 3600,
        project_id: 1,
        name: "Description",
    });
});

onRpc("has_group", () => true);
onRpc("get_running_timer", () => ({
    id: 10,
    start: 5740, // 01:35:40
    project_id: 1,
    name: "Description",
    has_helpdesk_team: true,
    helpdesk_ticket_id: false,
    task_id: false,
    step_timer: 30,
}));

test("Timer already running with helpdesk ticket", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["project_id", "helpdesk_ticket_id"],
        config: {
            views: [[false, "search"]],
        },
    });
    await animationFrame();
    expect('div[name="task_id"] input').toHaveCount(0);
    expect('div[name="helpdesk_ticket_id"]').toHaveCount(1, {
        message: "a ticket field should be rendered",
    });
    await contains('div[name="helpdesk_ticket_id"] input').edit("Ticket 4");
    await click(".o_stop_timer_button");
});
