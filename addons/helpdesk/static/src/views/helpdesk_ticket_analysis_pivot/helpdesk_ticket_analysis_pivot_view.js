import { registry } from "@web/core/registry";
import { pivotView } from "@web/views/pivot/pivot_view";
import { HelpdeskTicketAnalysisPivotRenderer } from "./helpdesk_ticket_analysis_pivot_renderer";

export const helpdeskTicketAnalysisPivotView = {
    ...pivotView,
    Renderer: HelpdeskTicketAnalysisPivotRenderer,
};

registry.category("views").add("helpdesk_ticket_analysis_pivot", helpdeskTicketAnalysisPivotView);
