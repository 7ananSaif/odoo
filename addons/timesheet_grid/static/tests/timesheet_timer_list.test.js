import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { waitFor, click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import {
    contains,
    fieldInput,
    fields,
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
    selectFieldDropdownItem,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";
import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { clickTimerButton, timerHeaderSelectors } from "./timesheet_grid_timer_helpers";

defineTimesheetModels();
beforeEach(() => {
    patchSession();

    HRTimesheet._views.grid = HRTimesheet._views.grid
        .replace('js_class="timesheet_grid"', 'js_class="timer_timesheet_grid"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
});

describe.current.tags("desktop");

test("hr.timesheet (list)(timer): basics", async () => {
    HRTimesheet._records = [
        { id: 1, name: "yop" },
        { id: 2, name: "bip" },
    ];
    await mountView({
        type: "list",
        resModel: "account.analytic.line",
        arch: `
            <list js_class="timesheet_timer_list">
                <field name="name"/>
            </list>
        `,
    });

    expect(".o_timesheet_timer_list_view").toHaveCount(1);
    expect(".pinned_header .timesheet-timer").toHaveCount(1);
    expect(".o_pager").toHaveCount(1);
    expect(".o_pager").toHaveText("1-2 / 2");
});

test("timesheet.grid (list)(timer): start & stop", async () => {
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the list view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (list)(timer): start & stop, view is grouped", async () => {
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
        groupBy: ["project_id"],
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the list view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (list)(timer): start & stop, view is grouped multiple times", async () => {
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
        groupBy: ["project_id", "task_id", "name"],
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the list view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (list)(timer): start the timer without a valid project", async () => {
    onRpc(({ method }) => {
        if (method === "action_start_new_timesheet_timer") {
            return false;
        }
    });
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(".o_stop_timer_button");
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the list view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor("div.o_notification_manager span:contains('Missing Required Fields')");
    expect("div.o_notification_manager span:contains('Missing Required Fields')").toHaveCount(1, {
        message:
            "The default notification of 'required fields' of a Many2one relation should be raised.",
    });
});

test("timesheet.grid (list)(timer): start, edit name and stop", async () => {
    onRpc("action_timer_stop", function ({ args }) {
        const timesheetId = args[0];
        expect(this.env["account.analytic.line"].read(timesheetId, ["name"])[0].name).toBe("test");
    });
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the list view, the timesheet in the header should be editable.",
    });
    await contains("div.pinned_header div[name=name] input").edit("test", { confirm: false });
    await clickTimerButton("stop");
});

test("hr.timesheet (list)(timer): switch view with GroupBy and start the timer", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "grid"],
            [false, "list"],
        ],
        context: { group_by: ["project_id", "task_id"] },
    });

    await click(".o_switch_view.o_list");
    await animationFrame();
    await clickTimerButton("start");
    expect(timerHeaderSelectors.start).toHaveCount(0, {
        message: "Timer should be running",
    });
});

test("hr.timesheet (list)(timer): start timer, set fields and switch view", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "list"],
            [false, "grid"],
        ],
    });

    await clickTimerButton("start");
    await fieldInput("name").edit("Test", { confirm: false });
    await selectFieldDropdownItem("task_id", "BS task");

    await click(".o_switch_view.o_grid");
    await animationFrame();
    expect(".o_field_char[name='name'] input").toHaveValue("Test", {
        message: "Description shouldn't have changed by switching view",
    });
    expect(".o_field_many2one[name='task_id'] input").toHaveValue("BS task", {
        message: "Task shouldn't have changed by switching view",
    });
});

test("hr.timesheet (list)(timer): unlink timesheet through timesheet_uom_timer widget", async () => {
    HRTimesheet._fields.is_timer_running = fields.Boolean();
    HRTimesheet._records[0].is_timer_running = true;
    HRTimesheet._views.list = HRTimesheet._views.list.replace(
        '<field name="unit_amount" />',
        `<field name="unit_amount" widget="timesheet_uom_timer"/>
         <field name="is_timer_running" column_invisible="1"/>
         <field name="display_timer" column_invisible="1"/>`
    );
    onRpc(({ method }) => {
        if (method === "get_running_timer") {
            return {
                id: 1,
                step_timer: 30,
            };
        }
    });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[false, "list"]],
    });
    await animationFrame();

    expect(".o_icon_button").toHaveProperty("title", "Stop", {
        message: "The timer stop button should be visible",
    });

    // Stop the timer using the list view (timesheet_uom_timer widget)
    await click(".o_icon_button");
    await animationFrame();

    expect('div[name="project_id"] input').toHaveCount(0, {
        message: "The project input should not exist",
    });
});

test("timesheet.grid (list)(time): retain edited time after focus change", async () => {
    await mountView({
        type: "list",
        resModel: HRTimesheet._name,
        arch: `<list editable="bottom" js_class="timesheet_timer_list">
                <field name="name" />
                <field name="unit_amount" widget="timesheet_uom_timer" />
            </list>`,
    });
    const targetRow = ".o_data_row:nth-child(1)";
    await click(`${targetRow} .o_list_number`);
    await contains(`${targetRow} .o_list_number input`).edit("45", { confirm: false });
    await click(`${targetRow} .o_list_char`);
    await animationFrame();
    expect(`${targetRow} .o_list_number input`).toHaveValue("45:00");
});
