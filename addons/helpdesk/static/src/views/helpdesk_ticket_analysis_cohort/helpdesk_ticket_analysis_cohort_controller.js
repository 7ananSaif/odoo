import { CohortController } from "@web_cohort/cohort_controller";
import { Domain } from "@web/core/domain";

export class HelpdeskTicketAnalysisCohortController extends CohortController {
    openView(domain, views, context) {
        for (const leaf of domain) {
            if (Array.isArray(leaf) && leaf[0] === "ticket_id") {
                leaf[0] = "id";
            }
        }
        const newDomain = Domain.removeDomainLeaves(domain, [
            "rating_avg",
            "rating_last_value",
            "ticket_close_hours",
            "ticket_deadline_hours",
            "ticket_open_hours",
            "ticket_assignation_hours"
        ]).toList();

        this.actionService.doAction({
            context,
            domain: newDomain,
            name: "Tickets",
            res_model: "helpdesk.ticket",
            target: "current",
            type: "ir.actions.act_window",
            views,
        }, {
            viewType: "list",
        });
    }
}
