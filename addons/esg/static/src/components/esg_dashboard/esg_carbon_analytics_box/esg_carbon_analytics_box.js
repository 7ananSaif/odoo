import { EsgGraphDashboard } from "@esg/components/esg_dashboard/esg_graph_dashboard/esg_graph_dashboard";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class EsgCarbonAnalyticsBox extends Component {
    static template = "esg.CarbonAnalyticsBox";
    static components = { EsgGraphDashboard };
    static props = {
        data: Object,
    };

    setup() {
        this.actionService = useService("action");
    }

    openEmissionsViews() {
        this.actionService.doAction("esg.action_emitted_emission_report_views");
    }

    openEmissionsForm() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "esg.other.emission",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openUnassignedEmissions() {
        this.actionService.doAction({
            name: _t("Emissions to define"),
            type: "ir.actions.act_window",
            res_model: "esg.carbon.emission.report",
            views: [[false, "list"]],
            context: {
                search_default_missing_factor_emissions: true,
            },
        });
    }
}
