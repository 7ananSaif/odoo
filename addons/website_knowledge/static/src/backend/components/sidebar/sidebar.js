import { KnowledgeSidebar } from "@knowledge/components/sidebar/sidebar";
import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";

patch(KnowledgeSidebar.prototype, {
    setup() {
        super.setup();
        this.originalRootId = this.props.record.data.root_article_id.id;
    },
    get searchDomain() {
        const originalDomain = super.searchDomain;
        return Domain.or([
            originalDomain,
            ["&", ["website_published", "=", true], ["id", "child_of", this.originalRootId]],
        ]).toList({});
    },
});
