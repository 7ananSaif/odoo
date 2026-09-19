import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class EsgProjectInitiativesBox extends Component {
    static template = "esg_project.InitiativesBox";
    static props = {
        data: Object,
    };

    setup() {
        this.actionService = useService("action");
    }

    openViewProject() {
        this.actionService.doAction("esg_project.esg_initiatives_server_action");
    }

    openTaskForm() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_project_id: this.props.data.project_id,
            },
        });
    }
}
