import { registry } from "@web/core/registry";
import { hrTimesheetGraphView } from "@hr_timesheet/views/timesheet_graph/timesheet_graph_view";
import { HelpdeskTicketAnalysisGraphRenderer } from "@helpdesk/views/helpdesk_ticket_analysis_graph/helpdesk_ticket_analysis_graph_renderer";

registry.category("views").add("hr_timesheet_helpdesk_ticket_analysis_graph", {
    ...hrTimesheetGraphView,
    Renderer: HelpdeskTicketAnalysisGraphRenderer,
});
