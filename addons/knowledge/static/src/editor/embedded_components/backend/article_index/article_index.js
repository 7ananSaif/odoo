import { onWillStart, useState, useSubEnv, Component } from "@odoo/owl";
import {
    getEmbeddedProps,
    useEmbeddedState,
    StateChangeManager,
} from "@html_editor/others/embedded_component_utils";
import {
    EmbeddedComponentToolbar,
    EmbeddedComponentToolbarButton,
} from "@html_editor/others/embedded_components/core/embedded_component_toolbar/embedded_component_toolbar";
import { ArticleIndexList } from "@knowledge/editor/embedded_components/backend/article_index/article_index_list";
import { useService } from "@web/core/utils/hooks";
import { KeepLast } from "@web/core/utils/concurrency";

export class EmbeddedArticleIndexComponent extends Component {
    static template = "knowledge.EmbeddedArticleIndex";
    static components = {
        ArticleIndexList,
        EmbeddedComponentToolbar,
        EmbeddedComponentToolbarButton,
    };
    static props = {
        host: { type: Object },
        articles: { type: Object, optional: true },
        showAllChildren: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.embeddedState = useEmbeddedState(this.props.host);
        this.keepLastFetch = new KeepLast();
        this.state = useState({
            loading: false,
            key: 0,
        });

        useSubEnv({
            reloadArticleIndex: () => this.loadArticleIndex(),
        });

        onWillStart(async () => {
            if (this.embeddedState.articles === undefined) {
                this.loadArticleIndex({ firstLoad: true });
            }
        });
    }

    /**
     * @param {integer} resId
     * @param {Boolean} showAllChildren
     * @returns {Array[Object]}
     */
    async fetchAllArticles(resId, showAllChildren) {
        const domain = [
            ["parent_id", !showAllChildren ? "=" : "child_of", resId],
            ["is_article_item", "=", false],
        ];
        const { records } = await this.orm.webSearchRead("knowledge.article", domain, {
            specification: {
                display_name: {},
                parent_id: {},
            },
            order: "sequence",
        });
        return records;
    }

    async loadArticleIndex({ showAllChildren = undefined, firstLoad = false } = {}) {
        this.state.loading = true;
        if (showAllChildren === undefined) {
            showAllChildren = this.embeddedState.showAllChildren;
        }
        const resId = this.env.model.root.resId;
        const promise = this.fetchAllArticles(resId, showAllChildren);
        const articles = await this.keepLastFetch.add(promise);
        if (firstLoad && this.embeddedState.articles !== undefined) {
            // Articles were provided by a collaborator before
            // the first load was finished, discard loaded articles.
            this.state.loading = false;
            return;
        }
        /**
         * @param {integer} parentId
         * @returns {Object}
         */
        const buildIndex = (parentId) => {
            return articles
                .filter((article) => {
                    return article.parent_id && article.parent_id === parentId;
                })
                .map((article) => {
                    return {
                        id: article.id,
                        name: article.display_name,
                        childIds: buildIndex(article.id),
                    };
                });
        };
        this.state.loading = false;
        this.embeddedState.showAllChildren = showAllChildren;
        this.embeddedState.articles = buildIndex(resId);
        this.env.bus.trigger("KNOWLEDGE:RELOAD_SIDEBAR", {});
    }

    async onSwitchModeBtnClick() {
        await this.loadArticleIndex({
            showAllChildren: !this.embeddedState.showAllChildren,
        });
        this.state.key++; // restart the `ArticleIndexList` component to update
                          // the `nest` static option.
    }

    async openTemplatePicker() {
        const record = this.env.model.root;
        const templates = await this.orm.call("knowledge.article", "get_suggested_templates", [
            [record.resId],
        ]);
        this.env.bus.trigger("KNOWLEDGE:OPEN_ANNEXE_TEMPLATE_PICKER", {
            articles: [],
            templates: templates,
            onLoadArticle: () => {},
            /** @param {integer} templateId */
            onLoadTemplate: async (templateId) => {
                const articleIds = await this.orm.call(
                    "knowledge.article",
                    "load_suggested_template",
                    [record.resId, templateId]
                );
                if (articleIds?.length) {
                    await this.loadArticleIndex();
                    await this.env.openArticle(articleIds[0]);
                }
            },
            onDeleteArticle: () => {},
            /** @param {integer} templateId */
            onDeleteTemplate: async (templateId) => {
                await this.orm.unlink("knowledge.article", [templateId]);
            },
        });
    }

    async addChildToArticle() {
        const [articleId] = await this.orm.create("knowledge.article", [
            {
                parent_id: this.env.model.root.resId,
            },
        ]);
        await this.env.openArticle(articleId);
    }
}

export const articleIndexEmbedding = {
    name: "articleIndex",
    Component: EmbeddedArticleIndexComponent,
    getStateChangeManager: (config) => {
        return new StateChangeManager(config);
    },
    getProps: (host) => {
        return {
            host,
            ...getEmbeddedProps(host),
        };
    },
};
