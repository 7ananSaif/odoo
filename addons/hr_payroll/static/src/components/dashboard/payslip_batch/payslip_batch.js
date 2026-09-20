import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { useOpenPayRun } from "../../../views/payslip_run_hook";

export class PayrollDashboardPayslipBatch extends Component {
    static template = "hr_payroll.PayslipBatch";
    static props = ["batches"];

    setup() {
        this.actionService = useService("action");
        this.openPayRun = useOpenPayRun();
    }

    /**
     * Handles clicking on the title
     */
    onClickTitle() {
        this.actionService.doAction("hr_payroll.action_hr_payslip_run");
    }

    getColorFromState(state) {
        const colorMap = {
            New: "text-bg-info",
            Confirmed: "text-bg-warning",
            Done: "text-bg-success",
            Paid: "text-bg-primary",
        };
        return colorMap[state] || "text-bg-info";
    }

    /**
     * Handles clicking on the line
     *
     * @param {number} batchID
     */
    onClickLine(batchID) {
        this.openPayRun({
            id: batchID
        });
    }
}
