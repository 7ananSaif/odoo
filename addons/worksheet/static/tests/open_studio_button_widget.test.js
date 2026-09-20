import { expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { EventBus } from "@odoo/owl";

import {
    asyncStep,
    mockService,
    mountView,
    onRpc,
    waitForSteps,
} from "@web/../tests/web_test_helpers";

import { defineWorksheetModels } from "./worksheet_models";

defineWorksheetModels();

test("Button opens studio", async () => {
    const _bus = new EventBus();
    const modelFormAction = {
        name: "fakeFormAction",
        view_mode: "list,form",
    };
    onRpc("worksheet.template", "get_x_model_form_action", () => {
        asyncStep("get_x_model_form_action");
        return modelFormAction;
    });
    mockService("action", {
        async doAction(action) {
            expect(action).toEqual(modelFormAction, {
                message: "action service must receive the doAction call",
            });
            return true;
        },
    });
    mockService("ui", (env) => {
        Object.defineProperty(env, "isSmall", {
            value: false,
        });
        return {
            bus: _bus,
            block: () => asyncStep("block ui"),
            unblock: () => asyncStep("unblock ui"),
        };
    });
    mockService("studio", () => ({
        open: (...args) => _bus.trigger("studio:open", args),
    }));

    await mountView({
        type: "form",
        resModel: "worksheet.template",
        resId: 1,
        arch: `
            <form>
                <header>
                    <widget name="open_studio_button"/>
                </header>
                <group>
                    <field name="hex_color" widget="color"/>
                </group>
            </form>`,
    });

    _bus.addEventListener("studio:open", asyncStep("open studio"));
    expect(".o_widget_open_studio_button button").toHaveCount(1, {
        message: "The widget button should be present in the view.",
    });
    await click(".o_widget_open_studio_button button");
    await waitForSteps(["open studio", "get_x_model_form_action", "block ui", "unblock ui"]);
});
