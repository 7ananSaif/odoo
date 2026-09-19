import { click } from "@odoo/hoot-dom";
import { animationFrame, delay } from "@odoo/hoot-mock";

export const timerHeaderSelectors = {
    header: ".timesheet-timer",
    start: ".btn_start_timer",
    stop: ".o_stop_timer_button",
    discard: ".o_discard_timer_button",
};

/**
 * Click on Start/stop/discard button
 *
 * @param {"start" | "stop" | "discard"} action
 *
 **/
export async function clickTimerButton(action) {
    const selector = `${timerHeaderSelectors.header} ${timerHeaderSelectors[action]}`;
    await click(selector);

    if (action !== "discard") {
        // add a delay for the debounce added on start/stop actions
        await delay(250);
    }
    await animationFrame();
}
