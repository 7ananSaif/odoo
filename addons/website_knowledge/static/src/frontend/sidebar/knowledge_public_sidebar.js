import { rpc } from "@web/core/network/rpc";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";
import { Transition } from "@web/core/transition";
import { useBus, useChildRef, useForwardRefToParent, useService } from "@web/core/utils/hooks";
import { ArticleSearchDialog } from "@knowledge/components/article_search_dialog/article_search_dialog";
import { KeepLast } from "@web/core/utils/concurrency";
import { router, routerBus } from "@web/core/browser/router";

import {
    Component,
    onMounted,
    onWillStart,
    useEffect,
    useExternalListener,
    useState,
    useSubEnv,
} from "@odoo/owl";

class KnowledgePublicResizablePanel extends ResizablePanel {
    static props = {
        ...ResizablePanel.props,
        handleRef: { type: Function },
    };

    setup() {
        super.setup();
        useForwardRefToParent("handleRef");
    }
}

class SidebarArticle {
    /**
     * @param {integer} id
     * @param {string} icon
     * @param {string} name
     */
    constructor(id, icon, name) {
        this.id = id;
        this.icon = icon;
        this.name = name;
        this.children = [];
        this.isUnfolded = false;
        this.childrenAreLoaded = false;
        this.parent = null;
    }

    async loadChildren() {
        const children = await rpc("/knowledge/public/children", { article_id: this.id });
        this.children = children.map((child) => new SidebarArticle(child.id, child.icon, child.name));
        this.childrenAreLoaded = true;
    }

    async toggleFold() {
        if (!this.isUnfolded && !this.childrenAreLoaded) {
            await this.loadChildren();
        }
        this.isUnfolded = !this.isUnfolded;
    }
}

export class KnowledgePublicSidebar extends Component {
    static template = "website_knowledge.publicSidebar";
    static components = { ResizablePanel: KnowledgePublicResizablePanel, Transition };
    static props = {
        onMounted: Function,
        subEnv: Object,
        viewState: Object,
    };

    setup() {
        useSubEnv(this.props.subEnv);
        this.rootArticle = useState(new SidebarArticle(null, null, null));
        this.articlesMap = new Map();
        this.record = useState(this.env.record);
        this.dialog = useService("dialog");
        this.keepLastSidebarLoad = new KeepLast();
        onWillStart(() => {
            this.loadSidebar();
        });
        onMounted(() => {
            this.props.onMounted();
        });
        useEffect(
            () => {
                const article = this.articlesMap.get(this.record.resId);
                if (this.props.viewState.showSidebar && !article?.isUnfolded) {
                    this.loadSidebar();
                }
            },
            () => [this.record.resId, this.props.viewState.showSidebar]
        );
        useBus(routerBus, "ROUTE_CHANGE", () => this.env.openArticle(router.current.resId));
        // Handle color while dragging
        this.handleRef = useChildRef();
        const mouseDownHandler = () => {
            this.handleRef.el.classList.add("o_knowledge_sidebar_active_handle");
        };
        useEffect(
            (el) => {
                if (el) {
                    el.addEventListener("mousedown", mouseDownHandler);
                    return () => el.removeEventListener("mousedown", mouseDownHandler);
                }
            },
            () => [this.handleRef.el]
        );
        useExternalListener(document, "mouseup", () => {
            this.handleRef.el?.classList.remove("o_knowledge_sidebar_active_handle");
        });
    }

    async loadSidebar() {
        const articles = await this.keepLastSidebarLoad.add(
            rpc("/knowledge/public/sidebar", {
                article_id: this.env.record.resId,
            })
        );
        this.articlesMap = new Map();
        articles.forEach((article) => {
            this.articlesMap.set(article.id, new SidebarArticle(article.id, article.icon, article.name));
        });
        articles.forEach((article) => {
            const currentArticle = this.articlesMap.get(article.id);
            const parent = this.articlesMap.get(article.parent_id);
            if (parent) {
                parent.children.push(currentArticle);
                currentArticle.parent = parent;
                if (!parent.isUnfolded) {
                    parent.isUnfolded = true;
                }
            } else {
                // no parent or parent not published -> article is subsite root
                Object.assign(this.rootArticle, currentArticle);
            }
        });
        // case where root was processed before its children articles
        if (this.rootArticle.children.length) {
            this.rootArticle.isUnfolded = true;
        }
    }

    openSearchDialog() {
        this.dialog.add(ArticleSearchDialog, {
            search: (searchValue) =>
                rpc(`/knowledge/public/search`, {
                    search_value: searchValue,
                    subsite_root_id: this.rootArticle.id,
                }),
            select: (article) => this.env.openArticle(article.id).then(() => this.loadSidebar()),
        });
    }
}
