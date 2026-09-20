import { HtmlMigrationsInteraction } from "@html_editor/public/html_migrations/html_migrations_interaction";
import { patch } from "@web/core/utils/patch";

patch(HtmlMigrationsInteraction, {
    selector: [
        HtmlMigrationsInteraction.selector,
        `.o_knowledge_public_view:has(.o_knowledge_behavior_anchor)`,
    ].join(","),
});
