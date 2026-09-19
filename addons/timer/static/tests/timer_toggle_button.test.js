import { expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click } from "@odoo/hoot-dom";
import { mountWithCleanup, onRpc, makeMockEnv } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { TimerToggleButton } from "@timer/component/timer_toggle_button/timer_toggle_button";

defineMailModels();

async function _test_timer_toggle_button(testState) {
    const action = `action_timer_${testState ? "stop" : "start"}`;
    const icon = testState ? "stop" : "play";
    const env = await makeMockEnv();
    onRpc((args) => {
        if (args.method === action) {
            expect.step(action);
        }
        return true;
    });
    const props = {
        name: "timer",
        context: {},
        record: {
            resModel: "timer.timer",
            model: {
                load() {
                    expect.step("load");
                },
            },
            data: {
                timer: testState,
            },
        },
    };
    await mountWithCleanup(TimerToggleButton, { env, props: props });
    await animationFrame();
    expect("button i").toHaveClass(`fa-${icon}-circle`, {
        message: "correct icon is used",
    });
    click("button i");
    await animationFrame();
    expect.verifySteps([action, "load"]);
}

test("TimerToggleButton true value state test", async () => {
    await _test_timer_toggle_button(true);
});

test("TimerToggleButton false value state test", async () => {
    await _test_timer_toggle_button(false);
});
