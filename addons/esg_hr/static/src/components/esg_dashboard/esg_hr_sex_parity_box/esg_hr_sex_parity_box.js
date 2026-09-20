import { EsgGraphDashboard } from "@esg/components/esg_dashboard/esg_graph_dashboard/esg_graph_dashboard";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class EsgHrSexParityBox extends Component {
    static template = "esg_hr.SexParityBox";
    static components = { EsgGraphDashboard };
    static props = {
        data: Object,
    };

    setup() {
        this.actionService = useService("action");
    }

    openEmployeeReportLeadershipViews() {
        this.actionService.doAction("esg_hr.action_esg_employee_report_sex_parity");
    }

    get overallPayGapPercentage() {
        if (this.props.data.overall_pay_gap === false) {
            return _t("N/A");
        }
        return _t("%(overall_pay_gap)s%", { overall_pay_gap: this.props.data.overall_pay_gap });
    }
}
