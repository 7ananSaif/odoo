import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("helpdesk_livechat_info_panel_tour", {
    steps: () => [
        {
            trigger: ".o-mail-DiscussContent-threadName[title='Parent Partner']",
        },
        {
            trigger: ".o-mail-ActionPanel-header:contains(Information)",
        },
        {
            trigger: ".o-mail-ActionPanel span:contains(Ticket 1)",
        },
        {
            trigger: ".o-mail-ActionPanel span:contains(Ticket 2)",
        },
        {
            trigger: ".o-mail-ActionPanel span:not(:contains(Ticket Not Related))",
        },
    ],
});
