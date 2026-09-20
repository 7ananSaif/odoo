class HelpdeskSearchTicketSteps {
    /**
     * This method is meant to be overridden because its step behavior
     * changes when other modules are installed. E.g., after installing
     * `website_helpdesk`, the `beforeunload` event may not trigger, causing
     * an error if `expectUnloadPage` is set.
     */
    _searchTickets() {
        return {
            content: "search Ticket",
            trigger: ".oi-search",
            run: "click",
            expectUnloadPage: true,
        };
    }
}

export default HelpdeskSearchTicketSteps;
