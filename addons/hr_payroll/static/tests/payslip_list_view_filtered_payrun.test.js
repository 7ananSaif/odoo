import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { findComponent, mountView } from "@web/../tests/web_test_helpers";
import { Record } from "@web/model/record";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";
import { PayslipListController } from "@hr_payroll/views/payslip_list/hr_payslip_list_controller";
import { PayRunCard } from "@hr_payroll/components/payrun_card/payrun_card";

describe.current.tags("desktop");
defineHrPayrollModels();

beforeEach(() => {
    mockDate("2025-01-01 12:00:00", +0);
});

test("Test context of PayRunCard", async () => {
    const view = await mountView({
        type: "list",
        resModel: "hr.payslip",
        context: {
            search_default_payslip_run_id: 1,
        },
    });
    const payslipListController = findComponent(
        view,
        (component) => component instanceof PayslipListController
    );
    const record = findComponent(
        view,
        (component) =>
            component instanceof Record &&
            findComponent(component, (subComponent) => subComponent instanceof PayRunCard)
    );
    expect(record.props.context).toEqual(payslipListController.props.context);
});

test("Test header buttons of payslip list view filtered by payrun", async () => {
    await mountView({
        type: "list",
        resModel: "hr.payslip",
        context: {
            search_default_payslip_run_id: 1,
        },
    });
    expect(".o_control_panel_main_buttons button").toHaveCount(1);
    expect(".o_list_button_add").toHaveText("New");
});
