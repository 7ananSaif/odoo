import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { mountView } from "@web/../tests/web_test_helpers";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";

describe.current.tags("desktop");
defineHrPayrollModels();

beforeEach(() => {
    mockDate("2025-01-01 12:00:00", +0);
});

test("Test header buttons of payslip list view", async () => {
    await mountView({
        type: "list",
        resModel: "hr.payslip",
    });
    expect(".o_control_panel_main_buttons button").toHaveCount(2);
    expect(".o_list_button_add").toHaveText("New Off-Cycle");
    expect(".o_control_panel_main_buttons button:eq(1)").toHaveText("Pay Run");
});
