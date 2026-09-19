import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("web_enterprise.test_studio_list_upsell", {
    steps: () => [
        {
            trigger: ".o_list_view",
        },
        {
            trigger: ".o_optional_columns_dropdown > button",
            run: "click",
        },
        {
            trigger: " .o-dropdown--menu .dropdown-item-studio",
        },
    ],
});

registry.category("web_tour.tours").add("web_enterprise.test_studio_no_list_upsell_if_blacklisted", {
    steps: () => [
        {
            trigger: ".o_list_view",
        },
        {
            trigger: ".o_optional_columns_dropdown > button",
            run: "click",
        },
        {
            trigger: ".o-dropdown--menu:not(:has(.dropdown-item-studio))",
        },
    ],
});
