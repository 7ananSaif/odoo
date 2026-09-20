import HelpdeskSearchTicketSteps from "@helpdesk/../tests/tours/helpdesk_search_ticket_steps";
import { registry } from "@web/core/registry";

const helpdeskSearchTicketSteps = new HelpdeskSearchTicketSteps();

registry.category("web_tour.tours").add("helpdesk_search_ticket_on_portal_tour", {
    url: "/my/tickets",
    steps: () => [
        {
            trigger: ".border-end",
            content: "click on dropdown.",
            run: "click",
        },
        {
            trigger: '.dropdown-menu a:contains("Search Tickets")',
            content: "select Search Tickets.",
            run: "click",
        },
        {
            content: "Type name of ticket",
            trigger: 'form input[name="search"]',
            run: "edit lamp stand",
        },
        helpdeskSearchTicketSteps._searchTickets(),
        {
            trigger: "table > tbody > tr a:has(span:contains(lamp stand))",
            content: "click on ticket.",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: "#chatterRoot:shadow div.o-mail-Thread-empty",
        },
    ],
});
