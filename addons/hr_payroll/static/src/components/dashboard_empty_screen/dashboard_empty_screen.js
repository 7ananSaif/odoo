import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";


export class DashboardEmptyScreen extends Component {
    static template = "hr_payroll.DashboardEmptyScreen";
    static props = {};

    setup(){
        this.action = useService("action");
    }

    openEmployeeCreate(){
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            views: [[false, "form"]],
            target: "current",
        });
    }
}
