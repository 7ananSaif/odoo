import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("portal_download_signed_document", {
    url: "/my",

    steps: () => [
        {
            content: "Click on signature requests.",
            trigger: "a[title='Signature requests']",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Click on sign button for request.",
            trigger: "a:contains(template_1_role)",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Click on Download button.",
            trigger: "a[title=Download]",
            run: "click",
        },
        {
            content: "Open all the signature requests",
            trigger: ".o_portal_submenu a:contains(Signature requests)",
            run: "click",
            expectUnloadPage: true,
        },
    ],
});
