import { registry } from "@web/core/registry";
import { graphView } from "@web/views/graph/graph_view";
import { HelpdeskTicketAnalysisGraphRenderer } from "./helpdesk_ticket_analysis_graph_renderer";

export const helpdeskTicketAnalysisGraphView = {
    ...graphView,
    Renderer: HelpdeskTicketAnalysisGraphRenderer,
};

registry.category("views").add("helpdesk_ticket_analysis_graph", helpdeskTicketAnalysisGraphView);
