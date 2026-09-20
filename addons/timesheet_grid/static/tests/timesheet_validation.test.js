import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mountView, onRpc } from "@web/../tests/web_test_helpers";

import { HRTimesheet, defineTimesheetModels } from "./hr_timesheet_models";

defineTimesheetModels();
onRpc("action_validate_timesheet", ({ method }) => {
    expect.step("action_validate_timesheet");
    return {
        params: {
            type: "danger",
            message: "dummy message",
        },
    };
});
describe.current.tags("desktop");

test("hr.timesheet (kanban): notification should be triggered on validation", async () => {
    HRTimesheet._records = [{ id: 1, unit_amount: 1 }];
    await mountView({
        type: "kanban",
        resModel: "account.analytic.line",
        arch: `
            <kanban js_class="timesheet_validation_kanban">
                <templates>
                    <t t-name="card">
                        <div><field name="unit_amount"/></div>
                    </t>
                </templates>
            </kanban>
        `,
    });

    await click(".o_control_panel_main_buttons button.btn-secondary");
    await animationFrame();
    expect(".o_notification:has(.o_notification_bar.bg-danger)").toHaveText("dummy message");
    expect.verifySteps(["action_validate_timesheet"]);
});

test("hr.timesheet (pivot): notification should be triggered on validation", async () => {
    HRTimesheet._records = [{ id: 1, unit_amount: 1 }];
    await mountView({
        type: "pivot",
        resModel: "account.analytic.line",
        arch: `
            <pivot js_class="timesheet_validation_pivot_view">
                <field name="unit_amount"/>
            </pivot>
        `,
    });

    await click(".o_pivot_buttons .btn");
    await animationFrame();
    expect(".o_notification:has(.o_notification_bar.bg-danger)").toHaveText("dummy message");
    expect.verifySteps(["action_validate_timesheet"]);
});
