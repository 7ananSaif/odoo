import { expect, test } from "@odoo/hoot";
import { makeMockEnv } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { TimerReactive } from "@timer/models/timer_reactive";

const { DateTime } = luxon;

defineMailModels();

test("timer_reactive handle displaying start time", async () => {
    const env = await makeMockEnv();
    const timerReactive = new TimerReactive(env);
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("00:00:00");

    const currentTime = DateTime.now();
    const timerStart = currentTime.minus({ seconds: 1 });
    timerReactive.computeOffset(currentTime);
    timerReactive.setTimer(0, timerStart, currentTime);
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("00:00:01");
});

test("timer_reactive handle displaying durations longer than 24h", async () => {
    const env = await makeMockEnv();
    const timerReactive = new TimerReactive(env);
    const currentTime = DateTime.now();
    const timerStart = currentTime.minus({ days: -2 });
    timerReactive.computeOffset(currentTime);
    timerReactive.setTimer(0, timerStart, currentTime);
    timerReactive.formatTime();
    expect(timerReactive.time).toBe("48:00:00");
});
