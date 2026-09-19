import { models } from "@web/../tests/web_test_helpers";

export class HrPayslip extends models.ServerModel {
    _name = "hr.payslip";

    _views = {
        search: `
            <search>
                <field name="payslip_run_id"/>
            </search>
        `,
        list: `
            <list js_class="hr_payroll_payslip_list">
                <field name="id"/>
                <field name="employee_id"/>
            </list>
        `,
    };
}
