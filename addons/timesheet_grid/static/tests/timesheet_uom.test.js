import { beforeEach, expect, test } from "@odoo/hoot";
import { queryFirst } from "@odoo/hoot-dom";
import { contains, mountView, serverState } from "@web/../tests/web_test_helpers";

import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";
import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";

defineTimesheetModels();
beforeEach(() => {
    patchSession();
    HRTimesheet._views.grid = HRTimesheet._views.grid.replace(
        'widget="float_time"',
        'widget="timesheet_uom"'
    );
    HRTimesheet._views["grid,1"] = HRTimesheet._views["grid,1"].replace(
        'widget="float_time"',
        'widget="timesheet_uom"'
    );
});

async function mountViewAndGetCell() {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["task_id", "project_id"],
    });
    return queryFirst(".o_grid_row:not(.o_grid_row_total,.o_grid_row_title,.o_grid_column_total)");
}

test("hr.timesheet (grid): timesheet_uom should be company related", async () => {
    const cell = await mountViewAndGetCell();

    expect(cell.textContent).toBe("0:00", {
        message: "float_time formatter should be used",
    });
    await contains(cell).hover();
    expect(cell.textContent).toBe("0:00", {
        message: "float_time formatter should be used",
    });
});

test("hr.timesheet (grid): timesheet_uom widget should be float_toggle if uom is days", async () => {
    serverState.companies[0].timesheet_uom_id = 2;
    const cell = await mountViewAndGetCell();

    expect(cell.textContent).toBe("0.00", {
        message: "float_toggle formatter should be used",
    });
    await contains(cell).hover();
    expect(cell.textContent).toBe("0.00", {
        message: "float_toggle formatter should be used",
    });
});

test("hr.timesheet (grid): timesheet_uom widget should be float_factor if uom is foo", async () => {
    serverState.companies[0].timesheet_uom_id = 3;
    const cell = await mountViewAndGetCell();

    expect(cell.textContent).toBe("0.00", {
        message: "float_factor formatter should be used",
    });
    await contains(cell).hover();
    expect(cell.textContent).toBe("0.00", {
        message: "float_factor formatter should be used",
    });
});

test.tags("desktop");
test("hr.timesheet (grid): clicking on the magnifying glass shouldn't toggle the cell", async () => {
    serverState.companies[0].timesheet_uom_id = 2;
    const cell = await mountViewAndGetCell();

    expect(cell.textContent).toBe("0.00", {
        message: "Initial cell content should be 0.00",
    });
    await contains(cell).hover();
    await contains(".o_grid_search_btn").click();
    expect(cell.textContent).toBe("0.00", {
        message: "Clicking on the magnifying glass shouldn't alter the content of the cell",
    });
});
