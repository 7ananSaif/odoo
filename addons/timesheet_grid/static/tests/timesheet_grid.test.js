import { beforeEach, expect, test } from "@odoo/hoot";
import { click, queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
    removeFacet,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";

defineTimesheetModels();
beforeEach(patchSession);

function checkSectionsColsOverAndDownTime() {
    expect(queryAllTexts(".o_grid_section.text-warning")).toEqual(["25:00", "10:00"], {
        message: "Mario has overtime (25h00 > 8h00) and (10h00 > 8h00)",
    });
    expect(".o_grid_section.o_grid_row_total.text-bg-warning").toHaveCount(1, {
        message: "Mario has overtime (35h00 > 16h00)",
    });

    expect(queryAllTexts(".o_grid_section.text-danger")).toEqual(["2:30", "0:00"], {
        message: "Luigi has downtime (2h30 < 8h00) and (0h00 < 8h00)",
    });
    expect(".o_grid_section.o_grid_row_total.text-bg-danger").toHaveCount(1, {
        message: "Luigi has downtime (2h30 < 12h00)",
    });

    expect(".o_grid_section.o_grid_row_total.text-bg-success").toHaveCount(2, {
        message: "Yoshi (5h30 = 5h30) and Toad (0h00 = 0h00) are in time.",
    });
}

test("hr.timesheet (grid): no groupby", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
    });

    expect(".o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(6, {
        message: "There should be 6 employee avatars",
    });
    expect(".o_grid_component_timesheet_many2one").toHaveCount(11, {
        message: "There should be 11 many2one widgets",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "There should be 6 rows",
    });

    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): groupby employee", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["employee_id"],
    });

    expect(".o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(4, {
        message: "There should be 4 employee avatars",
    });
    expect(".o_grid_row_title").toHaveCount(4, {
        message: "There should be 4 rows",
    });

    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): groupby employee > task", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["employee_id", "task_id"],
    });

    expect(".o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(6, {
        message: "There should be 6 employee avatars",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "There should be 6 rows",
    });
    expect(".o_grid_component_timesheet_many2one").toHaveCount(5, {
        message: "There should be 5 many2one widgets",
    });
    expect(".o_grid_component").toHaveCount(11, {
        message: "There should be 11 widgets",
    });

    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): groupby task > employee", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["task_id", "employee_id"],
    });

    expect(".o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(6, {
        message: "There should be 6 employee avatars",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "There should be 4 rows",
    });
    expect(".o_grid_component_timesheet_many2one").toHaveCount(6, {
        message: "There should be 6 many2one widgets",
    });
    expect(".o_grid_component_timesheet_many2one .o_grid_no_data").toHaveCount(1, {
        message: "There should be one many2one widget with no data",
    });
    expect(".o_grid_component").toHaveCount(12, {
        message: "There should be 12 widgets",
    });
    expect(".o_grid_row.text-danger").toHaveText("-3:30");
});

test("hr.timesheet (grid): employee section - no groupby", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: [] },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).toHaveCount(4, {
        message: "There should be 4 sections with employee avatar",
    });
    expect(".o_grid_component_timesheet_many2one").toHaveCount(11, {
        message: "There should be 11 many2one widgets in total",
    });
    expect(
        ".o_grid_row_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).not.toHaveCount(null, {
        message: "No employee avatar should be displayed in the rows",
    });
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one").toHaveCount(11, {
        message: "The 11 many2one widgets should be displayed in the rows",
    });
    expect(".o_grid_section_title .o_grid_component_timesheet_many2one").not.toHaveCount(null, {
        message: "No many2one widgets should be displayed in the sections",
    });
    expect(".o_grid_section_title").toHaveCount(4, {
        message: "4 sections should be rendered in the grid view",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "There should be 6 rows displayed in the grid",
    });
    expect(".o_grid_add_line .btn-link").toHaveCount(2, {
        message: "There should be 2 Add a line button",
    });

    checkSectionsColsOverAndDownTime();
    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): employee section - groupby employee", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: ["employee_id"] },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).not.toHaveCount(null, {
        message: "No employee avatar should be displayed in the sections",
    });
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(
        4,
        { message: "There should be 4 rows with employee avatar" }
    );
    expect(".o_grid_component_timesheet_many2one").not.toHaveCount(null, {
        message: "No many2one widgets should be rendered",
    });
    expect(".o_grid_section_title").not.toHaveCount(null, {
        message: "No sections should be displayed in the grid",
    });
    expect(".o_grid_row_title").toHaveCount(4, {
        message: "4 rows should be rendered in the grid view",
    });

    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): employee section - groupby employee > task", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: ["employee_id", "task_id"] },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).toHaveCount(4, {
        message: "There should be 4 sections with employee avatar",
    });
    expect(".o_grid_component_timesheet_many2one").toHaveCount(6, {
        message: "There should be 6 many2one widgets in total",
    });
    expect(".o_grid_component_timesheet_many2one .o_grid_no_data").toHaveCount(1, {
        message: "There should be one many2one widget with no data",
    });
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(
        0,
        {
            message: "No employee avatar should be displayed in the rows",
        }
    );
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one").toHaveCount(6, {
        message: "The 6 many2one widgets should be displayed in the rows",
    });
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one .o_grid_no_data").toHaveCount(
        1,
        {
            message: "There should be one many2one widget with no data",
        }
    );
    expect(".o_grid_section_title .o_grid_component_timesheet_many2one").toHaveCount(0, {
        message: "No many2one widgets should be displayed in the sections",
    });
    expect(".o_grid_section_title").toHaveCount(4, {
        message: "4 sections should be rendered in the grid view",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "There should be 6 rows displayed in the grid",
    });

    checkSectionsColsOverAndDownTime();
    expect(queryAllTexts(".o_grid_row.text-danger")).toEqual(["-3:30", "25:00"]);
});

test("hr.timesheet (grid): employee section - groupby task > employee", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: ["task_id", "employee_id"] },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).toHaveCount(0, {
        message: "No employee avatar should be displayed in the sections",
    });
    expect(".o_grid_row_title .o_grid_component_timesheet_many2one_avatar_employee").toHaveCount(
        6,
        {
            message: "There should be 4 rows with employee avatar",
        }
    );
    expect(".o_grid_component_timesheet_many2one").toHaveCount(6, {
        message: "6 many2one widgets should be rendered",
    });
    expect(".o_grid_component_timesheet_many2one .o_grid_no_data").toHaveCount(1, {
        message: "There should be one many2one widget with no data",
    });
    expect(".o_grid_section_title").toHaveCount(0, {
        message: "No sections should be displayed in the grid",
    });
    expect(".o_grid_row_title").toHaveCount(6, {
        message: "6 rows should be rendered in the grid view",
    });
    expect(".o_grid_row.text-danger").toHaveText("-3:30");
});

test("hr.timesheet (grid): avatar widget shouldn't display overtime if period includes today", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: [] },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).toHaveCount(4, {
        message: "There should be 4 sections with employee avatar",
    });
    expect(".o_grid_section_title .o_timesheet_overtime_indication").toHaveCount(0, {
        message: "No overtime indication should be displayed",
    });
});

test("hr.timesheet (grid): avatar widget should display hours in gray if all the hours were performed", async () => {
    mockDate("2017-01-31 00:00:00", 0);
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { group_by: [], grid_anchor: "2017-01-25" },
    });

    expect(
        ".o_grid_section_title .o_grid_component_timesheet_many2one_avatar_employee"
    ).toHaveCount(4, {
        message: "There should be 4 sections with employee avatar",
    });
    expect(".o_grid_section_title .o_timesheet_overtime_indication").toHaveCount(3, {
        message: "All the avatar should have a timesheet overtime indication displayed except one",
    });

    const sectionsTitleNodes = queryAll(".o_grid_section_title");
    const sectionWithDangerOvertimeTextContents = [];
    const sectionWithSuccessOvertimeTextContents = [];
    const sectionWithoutOvertimeTextContents = [];
    for (const node of sectionsTitleNodes) {
        const overtimeNode = queryFirst(".o_timesheet_overtime_indication", { root: node });
        if (overtimeNode) {
            if (overtimeNode.classList.contains("text-danger")) {
                sectionWithDangerOvertimeTextContents.push(node.textContent);
            } else {
                sectionWithSuccessOvertimeTextContents.push(node.textContent);
            }
        } else {
            sectionWithoutOvertimeTextContents.push(node.textContent);
        }
    }
    expect(sectionWithDangerOvertimeTextContents).toEqual(["Mario-198:00", "Toad-1.00"], {
        message:
            "Mario and Toad have not done all his working hours (the overtime indication for Toad is formatted in float since uom is Days and not hours)",
    });
    expect(sectionWithSuccessOvertimeTextContents).toEqual(["Yoshi+04:00"], {
        message: "Yoshi should have done his working hours and even more",
    });
    expect(sectionWithoutOvertimeTextContents).toEqual(["Luigi"], {
        message: "Luigi should have done his working hours without doing extra hours",
    });
});

test("hr.timesheet (grid): when in Next week date should be first working day", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: [],
    });

    await click(".o_grid_navigation_buttons > div > button > span.oi-arrow-right");
    await animationFrame();
    await click(".o_control_panel_main_buttons .o_grid_button_add");
    await animationFrame();
    expect(".modal").toHaveCount(1);
    expect(".modal .o_field_widget[name=date] button").toHaveValue("01/30/2017")
});

test("hr.timesheet (grid): when in Previous week date should be first working day", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: [],
    });

    await click(".o_grid_navigation_buttons > div > button > span.oi-arrow-left");
    await animationFrame();
    await click(".o_control_panel_main_buttons .o_grid_button_add");
    await animationFrame();
    expect(".modal").toHaveCount(1);
    expect(".modal .o_field_widget[name=date] button").toHaveValue("01/16/2017");
});

test("hr.timesheet (grid): display sample data and then data + fetch last validate timesheet date", async () => {
    HRTimesheet._views["grid,1"] = HRTimesheet._views["grid,1"].replace(
        "<grid",
        "<grid sample='1'"
    );

    onRpc(({ method }) => {
        if (method === "get_last_validated_timesheet_date") {
            expect.step("get_last_validated_timesheet_date");
        }
    });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[1, "grid"]],
        context: { search_default_nothing: 1 },
    });

    expect(".o_view_sample_data").toHaveCount(1);
    await removeFacet("Nothing");
    expect(".o_grid_sample_data").toHaveCount(0);
    expect(".o_grid_section_title").toHaveCount(4);
    expect.verifySteps(["get_last_validated_timesheet_date"]); // the rpc should be called only once
});

test("test timesheet grid when grouped by employees shows color code on timesheets", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[ false, "grid" ]],
        context: { group_by: [ "employee_id"] },
    });
    /**
     * Working periods of all employees in the test
     *
     * Mario - 6 hours on 25 and 27
     * Luigi - 8 hours on 24 and 25
     * Yoshi - 5.5 hours on 25
     * Toad - No working periods
     *
     * The timesheet here would be as (denoted as timesheet amount / that day work period length (corresponding color) )
     * ╔═══════╦════════════════╦═════════════════════════╦══════════════════╦══════════════════════╦═════════════════════╗
     * ║       ║ Jan 25         ║ Jan 26                  ║ Jan 27           ║ Jan 28               ║ Unit amount         ║
     * ╠═══════╬════════════════╬═════════════════════════╬══════════════════╬══════════════════════╬═════════════════════╣
     * ║ Luigi ║ 2:30 / 8 (Red) ║ 0                       ║ 0                ║ -3:30 / 0 (No color) ║ -1:00 / 8 (Red)     ║
     * ╠═══════╬════════════════╬═════════════════════════╬══════════════════╬══════════════════════╬═════════════════════╣
     * ║ Mario ║ 0              ║ 25 / 8 (Orange)         ║ 0                ║ 10 / 8 (Orange)      ║ 35 / 16 (Orange)    ║
     * ╠═══════╬════════════════╬═════════════════════════╬══════════════════╬══════════════════════╬═════════════════════╣
     * ║ Toad  ║ 0              ║ 0                       ║ 4 / 0 (No Color) ║ 0                    ║ 4 / 0 (Green)       ║
     * ╠═══════╬════════════════╬═════════════════════════╬══════════════════╬══════════════════════╬═════════════════════╣
     * ║ Yoshi ║ 0              ║ 5:30 / 5.30 (No color)  ║ 0                ║ 0                    ║ 5:30 / 5:30 (Green) ║
     * ╚═══════╩════════════════╩═════════════════════════╩══════════════════╩══════════════════════╩═════════════════════╝
     *
     **/
    expect(".o_grid_row .o_grid_cell_readonly span:contains(2:30)").toHaveClass("text-danger", {
        message: "The cell text should be red as that employee has working period of 8 hours but has timesheet of 2.5 hours",
    });
    expect(".o_grid_row .o_grid_cell_readonly span:contains(-3:30)").toHaveClass("text-900", {
        message: "The cell text should be normal as that employee has no working period of 8 hours but has timesheet of 2.5 hours",
    });
    expect(".o_grid_row .o_grid_cell_readonly span:contains(25:00)").toHaveClass("text-warning", {
        message: "The cell text should be orange as that employee has working period of 8 hours but has timesheet of 25 hours",
    });
    expect(".o_grid_row .o_grid_cell_readonly span:contains(10:00)").toHaveClass("text-warning", {
        message: "The cell text should be orange as that employee has working period of 8 hours but has timesheet of 10 hours",
    });
    expect(".o_grid_row .o_grid_cell_readonly span:contains(4:00)").toHaveClass("text-900", {
        message: "The cell text should be normal as that employee has no working period but has timesheet of 4 hours",
    });
    expect(".o_grid_row .o_grid_cell_readonly span:contains(5:30)").toHaveClass("text-success", {
        message: "The cell text should be normal as that employee has working period of 5.5 and has timesheet of 5.5 hours",
    });
    expect(queryFirst(".o_grid_row.o_grid_row_total span:contains(-1:00)").closest(".o_grid_row")).toHaveClass("text-bg-danger", {
        message: "The total cell should be red as that employee has working period of 8 and has timesheet of -1 hours",
    });
    expect(queryFirst(".o_grid_row.o_grid_row_total span:contains(35:00)").closest(".o_grid_row")).toHaveClass("text-bg-warning", {
        message: "The total cell should be orange as that employee has working period of 16 and has timesheet of 35 hours",
    });
    expect(queryFirst(".o_grid_row.o_grid_row_total span:contains(4:00)").closest(".o_grid_row")).toHaveClass("text-bg-success", {
        message: "The total cell should be green as that employee has no working period and has timesheet of 4 hours",
    });
    expect(queryFirst(".o_grid_row.o_grid_row_total span:contains(5:30)").closest(".o_grid_row")).toHaveClass("text-bg-success", {
        message: "The total cell should be green as that employee has working period of 5.5 and has timesheet of 5.5 hours",
    });
});
