import { expect, test } from "@odoo/hoot";
import { advanceTime, queryOne } from "@odoo/hoot-dom";
import { mountView, onRpc } from "@web/../tests/web_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";

import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";

const { DateTime } = luxon;
const now = DateTime.now();

defineTimesheetModels();

onRpc("get_server_time", () => serializeDateTime(now));

async function _testTimer(expectedRunning) {
    HRTimesheet._views.form = HRTimesheet._views.form.replace(
        '<field name="date"/>',
        '<field name="timer_start" widget="timer_start_field"/>'
    );

    const [record] = HRTimesheet._records;
    record.timer_start = serializeDateTime(now.minus({ days: 1 }));
    record.timer_pause = !expectedRunning && serializeDateTime(now.minus({ hours: 1 }));
    await mountView({
        type: "form",
        resModel: "account.analytic.line",
        resId: 1,
    });

    const timerStartInput = queryOne('div[name="timer_start"] span');
    const originalValue = timerStartInput.innerText;
    await advanceTime(2000);
    const currentValue = timerStartInput.innerText;
    if (expectedRunning) {
        expect(originalValue).not.toBe(currentValue, {
            message: "Value should have been updated after 1 second",
        });
    } else {
        expect(originalValue).toBe(currentValue, {
            message: "Value shouldn't have been updated after 1 second",
        });
    }
}

test("hr.timesheet (form): timer should be running when timer_pause is false", async () => {
    await _testTimer(false);
});

test("hr.timesheet (form): timer shouldn't be running when timer_pause is true", async () => {
    await _testTimer(true);
});
