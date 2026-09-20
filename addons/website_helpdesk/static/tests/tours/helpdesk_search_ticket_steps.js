import HelpdeskSearchTicketSteps from "@helpdesk/../tests/tours/helpdesk_search_ticket_steps";
import { patch } from "@web/core/utils/patch";

patch(HelpdeskSearchTicketSteps.prototype, {
    _searchTickets() {
        return {
            content: "search Ticket",
            trigger: ".oi-search",
            run: "click",
        };
    },
});
