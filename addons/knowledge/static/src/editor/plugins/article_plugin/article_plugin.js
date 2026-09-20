import { Plugin } from "@html_editor/plugin";
import { rightPos } from "@html_editor/utils/position";
import { ArticleSearchDialog } from "@knowledge/components/article_search_dialog/article_search_dialog";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";

const ARTICLE_LINKS_SELECTOR = ".o_knowledge_article_link";
export class KnowledgeArticlePlugin extends Plugin {
    static id = "article";
    static dependencies = ["history", "dom", "selection", "dialog"];
    resources = {
        user_commands: [
            {
                id: "insertArticle",
                title: _t("Article"),
                description: _t("Insert an Article shortcut"),
                icon: "fa-newspaper-o",
                run: this.addArticle.bind(this),
                isAvailable: isHtmlContentSupported,
            },
        ],
        powerbox_items: [
            {
                categoryId: "navigation",
                commandId: "insertArticle",
            },
        ],
        clean_for_save_handlers: this.cleanForSave.bind(this),
        normalize_handlers: this.normalize.bind(this),
    };

    setup() {
        super.setup();
        this.boundOpenArticle = this.openArticle.bind(this);
    }

    addArticle() {
        const recordInfo = this.config.getRecordInfo();
        let parentArticleId;
        if (recordInfo.resModel === "knowledge.article" && recordInfo.resId) {
            parentArticleId = recordInfo.resId;
        }
        const cursors = this.dependencies.selection.preserveSelection();
        const renderArticleLink = (id, displayName) => {
            const articleLinkBlock = renderToElement("knowledge.ArticleBlueprint", {
                href: `/knowledge/article/${id}`,
                articleId: id,
                displayName,
            });
            cursors.restore();
            this.dependencies.dom.insert(articleLinkBlock);
            this.dependencies.history.addStep();
            const [anchorNode, anchorOffset] = rightPos(articleLinkBlock);
            this.dependencies.selection.setSelection({ anchorNode, anchorOffset });
        };
        this.services.dialog.add(ArticleSearchDialog, {
            create: async (label) => {
                const articleIds = await this.services.orm.call(
                    "knowledge.article",
                    "article_create",
                    [],
                    {
                        title: label,
                        parent_id: parentArticleId,
                    }
                );
                const articleId = articleIds[0];
                renderArticleLink(articleId, `📄 ${label}`);
                if (parentArticleId) {
                    this.config.embeddedComponentInfo.env.bus.trigger(
                        "knowledge.sidebar.insertNewArticle",
                        {
                            articleId,
                            name: label,
                            icon: "📄",
                            parentId: parentArticleId,
                        }
                    );
                }
            },
            search: (searchValue) => {
                const params = { search_query: searchValue };
                let searchFunction = "get_user_sorted_articles";
                if (searchValue) {
                    searchFunction = "get_sorted_articles";
                    params.domain = [
                        "|",
                        ["is_article_visible", "=", true],
                        ["is_user_favorite", "=", true],
                    ];
                }
                return this.services.orm.call("knowledge.article", searchFunction, [[]], params);
            },
            searchEmptyQuery: true,
            select: (article) => renderArticleLink(article.id, article.displayName),
        }, { onClose: () => { this.dependencies.selection.focusEditable(); }});
    }

    scanForArticleLinks(element) {
        const articleLinks = [...element.querySelectorAll(ARTICLE_LINKS_SELECTOR)];
        if (element.matches(ARTICLE_LINKS_SELECTOR)) {
            articleLinks.unshift(element);
        }
        return articleLinks;
    }

    async openArticle(ev) {
        if (this.config.embeddedComponentInfo?.env?.openArticle) {
            const articleId = parseInt(ev.target.dataset.res_id);
            if (articleId) {
                ev.preventDefault();
                await this.config.embeddedComponentInfo.env.openArticle(articleId);
            }
        }
    }

    normalize(element) {
        const articleLinks = this.scanForArticleLinks(element);
        for (const articleLink of articleLinks) {
            articleLink.setAttribute("target", "_blank");
            articleLink.setAttribute("contenteditable", "false");
            articleLink.addEventListener("click", this.boundOpenArticle);
        }
    }

    cleanForSave({ root }) {
        const articleLinks = this.scanForArticleLinks(root);
        for (const articleLink of articleLinks) {
            articleLink.removeAttribute("contenteditable");
        }
    }

    destroy() {
        super.destroy();
        const articleLinks = this.scanForArticleLinks(this.editable);
        for (const articleLink of articleLinks) {
            articleLink.removeEventListener("click", this.boundOpenArticle);
        }
    }
}
