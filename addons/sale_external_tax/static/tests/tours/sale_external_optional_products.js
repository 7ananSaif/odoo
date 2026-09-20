import { registry } from "@web/core/registry";

// This tour relies on data created on the Python test.
registry.category("web_tour.tours").add("sale_external_optional_products", {
    url: "/my/quotes",
    steps: () => [
        {
            content: "open the test SO",
            trigger: 'a:contains("test")',
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_portal_sidebar_content h2:contains($):contains(10.00)",
        },
        {
            content: "Await communication shadow root to avoid rerenderer just before clicking",
            trigger: ":shadow button:contains(send)",
        },
        {
            content: "increase quantity of optional product",
            trigger: "tr:contains(optional product) .js_quantity_container .js_update_line_json[title='Add one']",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_portal_sidebar_content h2:contains($):contains(11.)",
        },
        {
            content: "Await communication shadow root to avoid rerenderer just before clicking",
            trigger: ":shadow button:contains(send)",
        },
        {
            content: "Check the quantity",
            trigger: "tr:contains(optional product) input.js_quantity:value(1)",
        },
        {
            content: "decrease quantity of the optional line",
            trigger: "tr:contains(optional product) .js_quantity_container .js_update_line_json[title='Remove one']",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_portal_sidebar_content h2:contains($):contains(10.)",
        },
    ],
});
