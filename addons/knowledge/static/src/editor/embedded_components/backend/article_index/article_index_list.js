import { Component, useRef } from "@odoo/owl";
import { useNestedSortable } from "@web/core/utils/nested_sortable";
import { useService } from "@web/core/utils/hooks";

export class ArticleIndexList extends Component {
    static template = "knowledge.ArticleIndexList";
    static props = {
        articles: { type: Object },
        isNested: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");

        useNestedSortable({
            ref: this.root,
            elements: "li",
            nest: this.props.isNested,
            onDrop: async ({ element, next, parent }) => {
                const options = {
                    parent_id: parent
                        ? parseInt(parent.getAttribute("data-article-id"))
                        : this.env.model.root.resId
                };
                if (next) {
                    options.before_article_id = parseInt(next.getAttribute("data-article-id"));
                }
                const id = parseInt(element.getAttribute("data-article-id"));
                await this.orm.call("knowledge.article", "move_to", [id], options);
                await this.env.reloadArticleIndex();
            },
        });
    }

    /** @param {integer} articleId */
    openArticle(articleId) {
        if (this.env.openArticle) {
            this.env.openArticle(articleId);
        }
    }

    /** @param {integer} articleId */
    async deleteArticle(articleId) {
        try {
            await this.orm.call("knowledge.article", "action_send_to_trash", [articleId]);
        } finally {
            await this.env.reloadArticleIndex();
        }
    }
}
