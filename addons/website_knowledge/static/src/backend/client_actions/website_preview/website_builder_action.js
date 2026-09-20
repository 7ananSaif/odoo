import { registry } from "@web/core/registry";

registry.category("isTopWindowURL").add("website_knowledge.website_builder_action", ({ host, pathname }) =>
    pathname && (
        pathname.startsWith("/knowledge/article/")
        || pathname.includes("/knowledge/home")
    )
);
