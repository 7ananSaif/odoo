import { expect, test } from "@odoo/hoot";
import { advanceTime, queryOne } from "@odoo/hoot-dom";
import { EventBus } from "@odoo/owl";
import { mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";

import {
    TimesheetDisplayTimer,
    TimesheetTimerFloatTimerField,
} from "@timesheet_grid/components/timesheet_display_timer/timesheet_display_timer";
import { defineTimesheetModels } from "./hr_timesheet_models";

const now = luxon.DateTime.utc();
defineTimesheetModels();
async function mountFloatTimerField(timerRunning) {
    await mountWithCleanup(TimesheetTimerFloatTimerField, {
        props: {
            value: 12 + 34 / 60 + (56 * timerRunning) / 3600,
            timerRunning,
            record: {
                isInvalid: () => false,
                model: { bus: new EventBus() },
                isFieldInvalid: () => {},
            },
            displayRed: false,
        },
    });
}

test("TimesheetTimerFloatTimerField should display seconds when timerRunning is true", async () => {
    await mountFloatTimerField(true);
    expect("input.o_input").toHaveValue("12:34:56", {
        message: `TimesheetTimerFloatTimerField should display seconds when the timer is running.`,
    });
});

test("TimesheetTimerFloatTimerField should not display seconds when timerRunning is false", async () => {
    await mountFloatTimerField(false);
    expect("input.o_input").toHaveValue("12:34", {
        message: `TimesheetTimerFloatTimerField should not display seconds when the timer is not running.`,
    });
});

onRpc("get_server_time", () => serializeDateTime(now));

async function _testTimesheetDisplayTimer(timerStart, timerPause) {
    const expectedRunning = !!timerStart && !timerPause;
    await mountWithCleanup(TimesheetDisplayTimer, {
        props: {
            name: "plop",
            record: {
                resModel: "dummy",
                isInvalid: () => false,
                model: { bus: new EventBus() },
                data: {
                    timer_start: timerStart,
                    timer_pause: timerPause,
                    plop: 1,
                },
                isFieldInvalid: () => {},
            },
        },
    });
    const timerStartInput = queryOne("input");
    const originalValue = timerStartInput.value;
    await advanceTime(2000);
    const currentValue = timerStartInput.value;

    let matcher = expect(originalValue);
    matcher = expectedRunning ? matcher.not : matcher;
    matcher.toBe(currentValue, {
        message: `The value should ${"not ".repeat(
            !expectedRunning
        )}have been updated after 1 second`,
    });
}

test("timesheet_display_timer should update the timer when timer_start is truthy and timer_pause is falsy", async () => {
    await _testTimesheetDisplayTimer(now.minus({ hours: 1 }), false);
});

test("timesheet_display_timer should not update the timer when timer_start is falsy", async () => {
    await _testTimesheetDisplayTimer(false, false);
});

test("timesheet_display_timer should not update the timer when timer_start and timer_pause are truthy", async () => {
    await _testTimesheetDisplayTimer(now.minus({ hours: 1 }), now.minus({ minutes: 30 }));
});
