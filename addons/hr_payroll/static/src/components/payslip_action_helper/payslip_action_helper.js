import { Component } from "@odoo/owl";


export class PayslipActionHelper extends Component {
    static template = "hr_payroll.PayslipActionHelper";
    static props = {
        payrunId: { type: Number, optional: true },
        onClickCreate: { type: Function },
        onClickGenerate: { type: Function },
    };
}
