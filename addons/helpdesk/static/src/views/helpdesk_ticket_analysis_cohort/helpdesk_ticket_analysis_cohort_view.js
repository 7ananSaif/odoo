import { registry } from "@web/core/registry";
import { cohortView } from "@web_cohort/cohort_view";
import { HelpdeskTicketAnalysisCohortController } from "./helpdesk_ticket_analysis_cohort_controller";

export const helpdeskTicketAnalysisCohortView = {
    ...cohortView,
    Controller: HelpdeskTicketAnalysisCohortController,
};

registry.category("views").add("helpdesk_ticket_analysis_cohort", helpdeskTicketAnalysisCohortView);
