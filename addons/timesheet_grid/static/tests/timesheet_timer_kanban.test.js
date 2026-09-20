import { beforeEach, describe, expect, test, getFixture } from "@odoo/hoot";
import { click, waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    fieldInput,
    fields,
    getService,
    mountWithCleanup,
    onRpc,
    selectFieldDropdownItem,
    contains,
    mountView,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";
import { serializeDateTime } from "@web/core/l10n/dates";

import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";
import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";

import { clickTimerButton, timerHeaderSelectors } from "./timesheet_grid_timer_helpers";

const now = luxon.DateTime.utc();
defineTimesheetModels();
beforeEach(() => {
    patchSession();
    HRTimesheet._views.kanban = /* xml */ `
        <kanban js_class="timesheet_timer_kanban">
            <templates>
                <field name="name"/>
                <t t-name="card">
                    <field name="employee_id"/>
                    <field name="project_id"/>
                    <field name="task_id"/>
                    <field name="date"/>
                    <field name="display_timer"/>
                    <field name="unit_amount"/>
                </t>
            </templates>
        </kanban>
    `;
    HRTimesheet._views.grid = HRTimesheet._views.grid
        .replace('js_class="timesheet_grid"', 'js_class="timer_timesheet_grid"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
});
describe.current.tags("desktop");

test("timesheet.grid (kanban)(timer): start & stop", async () => {
    await mountView({
        type: "kanban",
        resModel: "account.analytic.line",
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the kanban view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (kanban)(timer): start & stop, view is grouped", async () => {
    await mountView({
        type: "kanban",
        resModel: "account.analytic.line",
        groupBy: ["project_id"],
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the kanban view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (kanban)(timer): start & stop, view is grouped multiple times", async () => {
    await mountView({
        type: "kanban",
        resModel: "account.analytic.line",
        groupBy: ["project_id", "task_id", "name"],
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the kanban view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor(timerHeaderSelectors.start);
    expect("div.pinned_header input").toHaveCount(0);
});

test("timesheet.grid (kanban)(timer): start the timer with no valid project", async () => {
    onRpc(({ method }) => {
        if (method === "action_start_new_timesheet_timer") {
            return false;
        }
    });
    await mountView({
        type: "kanban",
        resModel: "account.analytic.line",
    });
    await waitFor(timerHeaderSelectors.start);
    await clickTimerButton("start");
    await waitFor(timerHeaderSelectors.stop);
    expect("div.pinned_header input").toHaveCount(3, {
        message:
            "When the timer is running in the kanban view, the timesheet in the header should be editable.",
    });

    await clickTimerButton("stop");
    await waitFor("div.o_notification_manager span:contains('Missing Required Fields')");
    expect("div.o_notification_manager span:contains('Missing Required Fields')").toHaveCount(1, {
        message:
            "The default notification of 'required fields' of a Many2one relation should be raised.",
    });
});

test("hr.timesheet (kanban)(timer): switch view with GroupBy and start the timer", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "grid"],
            [false, "kanban"],
        ],
        context: { group_by: ["project_id", "task_id"] },
    });

    await click(".o_switch_view.o_kanban");
    await animationFrame();
    await clickTimerButton("start");
    expect(timerHeaderSelectors.start).toHaveCount(0, {
        message: "Timer should be running",
    });
});

test("hr.timesheet (kanban)(timer): start timer, set fields and switch view", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "kanban"],
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

test("hr.timesheet (kanban)(timer): unlink timesheet through timesheet_uom_timer widget", async () => {
    HRTimesheet._fields.is_timer_running = fields.Boolean();
    HRTimesheet._records[0].is_timer_running = true;
    HRTimesheet._views.kanban = HRTimesheet._views.kanban.replace(
        '<field name="unit_amount"/>',
        '<field name="unit_amount" widget="timesheet_uom_timer"/><field name="is_timer_running" invisible="1"/>'
    );
    onRpc("get_running_timer", () => ({
        id: 1,
        step_timer: 30,
    }));

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[false, "kanban"]],
        context: {
            group_by: ["project_id", "task_id"],
            my_timesheet_display_timer: 1,
        },
    });
    await animationFrame();

    expect(".o_icon_button").toHaveProperty("title", "Stop", {
        message: "The timer stop button should be visible",
    });

    // Stop the timer using the kanban view (timesheet_uom_timer widget)
    await click(".o_icon_button");
    await animationFrame();

    expect('div[name="project_id"] input').toHaveCount(0, {
        message: "The project input should not exist",
    });
});

test("Timer should not start when adding new record", async () => {
    let timerStarted = false;

    onRpc("get_running_timer", () => ({ step_timer: 30 }));
    onRpc("action_start_new_timesheet_timer", () => {
        timerStarted = true;
        return false;
    });
    onRpc("get_daily_working_hours", () => ({}));
    onRpc("get_server_time", () => serializeDateTime(now));
    onRpc("get_create_edit_project_ids", () => []);

    HRTimesheet._views.list = /* xml */ `
        <list js_class="timesheet_timer_list" editable="bottom">
            <field name="project_id"/>
        </list>
    `;

    HRTimesheet._views.search = /* xml */ `
        <search>
            <field name="project_id"/>
        </search>
    `;

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "list"],
            [false, "kanban"],
        ],
    });

    await click(".o_list_button_add");
    await animationFrame();

    const fixture = getFixture();
    await contains(fixture.querySelector(".o-autocomplete--input")).click();
    await animationFrame();

    await contains(fixture.querySelector(".o-autocomplete .o-autocomplete--dropdown-item")).click();
    await animationFrame();

    await click(".o_switch_view.o_kanban");
    await animationFrame();

    expect(timerHeaderSelectors.start).toHaveCount(1);
    expect(timerStarted).toBe(false);
});
