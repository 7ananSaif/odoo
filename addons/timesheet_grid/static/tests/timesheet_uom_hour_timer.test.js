import { beforeEach, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame, runAllTimers } from "@odoo/hoot-mock";
import { fields, mountView, onRpc } from "@web/../tests/web_test_helpers";

import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";

defineTimesheetModels();
beforeEach(() => {
    patchSession();
    HRTimesheet._fields.is_timer_running = fields.Boolean();
    HRTimesheet._records = [
        {
            id: 1,
            unit_amount: 1,
            timer_start: false,
            timer_pause: false,
            display_timer: false,
            is_timer_running: false,
        },
        {
            id: 2,
            unit_amount: 1,
            timer_start: "2017-01-24 00:00:00",
            timer_pause: "2017-01-24 23:00:00",
            display_timer: true,
            is_timer_running: false,
        },
        {
            id: 3,
            unit_amount: 1,
            timer_start: "2017-01-24 00:00:00",
            timer_pause: false,
            display_timer: true,
            is_timer_running: true,
        },
    ];
});
const mountViewArgs = {
    type: "list",
    resModel: "account.analytic.line",
    arch: `
        <list editable="bottom">
            <field name="timer_start" />
            <field name="timer_pause" />
            <field name="display_timer" />
            <field name="is_timer_running" />
            <field
                name="unit_amount"
                widget="timesheet_uom_hour_timer"
                readonly="is_timer_running"
            />
        </list>
    `,
};
const iconPath = 'div[name="unit_amount"] button i';
function getNthRowPath(n) {
    return `.o_list_table .o_data_row:nth-of-type(${n})`;
}

test("hr.timesheet (list)(timer): button is displayed when display_timer is true", async () => {
    await mountView(mountViewArgs);
    expect(`${getNthRowPath(2)} ${iconPath}`).toBeVisible();
});

test("hr.timesheet (list)(timer): button is not displayed when in edition", async () => {
    await mountView(mountViewArgs);
    const secondRowPath = getNthRowPath(2);
    expect(`${secondRowPath} ${iconPath}`).toBeVisible();
    await click(`${secondRowPath} span`);
    await runAllTimers();
    expect(`${secondRowPath} ${iconPath}`).not.toHaveCount();
});

test("hr.timesheet (list)(timer): button is displayed when timer is running", async () => {
    await mountView(mountViewArgs);
    const thirdRowPath = getNthRowPath(3);
    expect(`${thirdRowPath} ${iconPath}`).toBeVisible();
    await click(`${thirdRowPath} span`);
    await animationFrame();
    expect(`${thirdRowPath} ${iconPath}`).toBeVisible();
});

test("hr.timesheet (list)(timer): button is not displayed when display_timer is false", async () => {
    await mountView(mountViewArgs);
    expect(`${getNthRowPath(1)} ${iconPath}`).not.toHaveCount();
});

test("hr.timesheet (list)(timer): icon is corresponding to is_timer_running", async () => {
    await mountView(mountViewArgs);
    expect(`${getNthRowPath(2)} ${iconPath}`).toHaveClass("fa-play");
    expect(`${getNthRowPath(3)} ${iconPath}`).toHaveClass("fa-stop");
});

test("hr.timesheet (list)(timer): correct rpc calls are performed (click play)", async () => {
    onRpc("action_timer_start", ({ method }) => {
        expect.step(method);
        return true;
    });

    await mountView(mountViewArgs);
    const secondRowIconPath = `${getNthRowPath(2)} ${iconPath}`;
    expect(secondRowIconPath).toHaveClass("fa-play");
    await click(secondRowIconPath);
    await animationFrame();
    expect.verifySteps(["action_timer_start"]);
});

test("hr.timesheet (list)(timer): correct rpc calls are performed (click stop)", async () => {
    onRpc("get_running_timer", ({ method }) => ({
        id: 3,
        unit_amount: 1,
        timer_start: "2017-01-24 00:00:00",
        timer_pause: false,
        display_timer: true,
        is_timer_running: true,
    }));
    onRpc("action_timer_stop", ({ method }) => {
        expect.step(method);
        return true;
    });

    await mountView(mountViewArgs);
    const thirdRowIconPath = `${getNthRowPath(3)} ${iconPath}`;
    expect(thirdRowIconPath).toHaveClass("fa-stop");
    await click(thirdRowIconPath);
    await animationFrame();
    expect.verifySteps(["action_timer_stop"]);
});
