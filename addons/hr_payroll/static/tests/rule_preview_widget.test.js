import { start, startServer, openFormView } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers"

defineHrPayrollModels()

test("Payroll rule preview", async () => {
    const pyEnv = await startServer();

    const ruleId = pyEnv["hr.salary.rule"].create({
        name: "Bonus",
        color: "#FF5733",
        bold: true,
        italic: true,
        underline: true,
    });

    await start();

    await openFormView("hr.salary.rule", ruleId, {
        arch: `
            <form>
                <group>
                    <field name="color"/>
                    <field name="bold"/>
                    <field name="underline"/>
                    <field name="italic"/>
                </group>
                <group name="preview">
                    <field name="name" widget="formatted_text_preview"/>
                </group>
            </form>
        `,
        resModel: "hr.salary.rule",
    });

    const styledTextEl = document.querySelector('div[name="name"] span');
    expect(styledTextEl).toHaveStyle({
        fontStyle: "italic",
        color: "rgb(255, 87, 51)",
        textDecorationLine: "underline",
        textDecorationColor: "rgb(255, 87, 51)",
    });
});
