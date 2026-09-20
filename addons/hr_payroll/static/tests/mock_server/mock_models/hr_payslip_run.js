import { models } from "@web/../tests/web_test_helpers";

export class HrPayslipRun extends models.ServerModel {
    _name = "hr.payslip.run";

    _views = {
        kanban: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                        <field name="date_start"/>
                        <field name="date_end"/>
                        <field name="payslip_count"/>
                        <field name="currency_id"/>
                        <field name="gross_sum"/>
                        <field name="net_sum"/>
                        <field name="state"/>
                    </t>
                </templates>
            </kanban>
        `,
    };

    _records = [
        {
            id: 1,
            name: "Basic Pay Run",
            state: "01_ready",
            currency_id: 1,
            display_name: "Basic Pay Run",
        },
    ];
}
