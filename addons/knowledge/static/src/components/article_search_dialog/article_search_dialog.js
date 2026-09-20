import { Dialog } from "@web/core/dialog/dialog";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { closestScrollableY } from "@web/core/utils/scrolling";
import { highlightText } from "@web/core/utils/html";
import { debounce } from "@web/core/utils/timing";
import { Component, markup, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";

export class ArticleSearchDialog extends Component {
    static template = "knowledge.ArticleSearchDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        select: Function,
        search: Function,
        create: { type: Function, optional: true },
        searchEmptyQuery: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            articles: [],
            searchValue: "",
            selectedIdx: 0,
            displayEmptySearch: false,
        });
        this.root = useRef("root");
        this.searchInput = useRef("searchInput");
        this.debouncedSearch = debounce(this.search, 500);
        useExternalListener(window, "pointerup", this.onWindowPointerUp);
        useHotkey("ArrowDown", () => this.onArrowDown(), {
            allowRepeat: true,
            bypassEditableProtection: true,
        });
        useHotkey("ArrowUp", () => this.onArrowUp(), {
            allowRepeat: true,
            bypassEditableProtection: true,
        });
        useHotkey("Enter", () => this.openSelectedArticle(), { bypassEditableProtection: true });
        useHotkey("escape", () => this.props.close());
        onWillStart(async () => {
            if (this.props.searchEmptyQuery) {
                await this.search("");
            }
        });
    }

    onArrowUp() {
        this.state.selectedIdx =
            this.state.selectedIdx > 0
                ? this.state.selectedIdx - 1
                : this.state.articles.length - 1;
    }

    onArrowDown() {
        this.state.selectedIdx =
            this.state.selectedIdx < this.state.articles.length - 1
                ? this.state.selectedIdx + 1
                : 0;
    }

    onArticleClick(articleIdx) {
        this.props.select(this.state.articles[articleIdx]);
        this.props.close();
    }

    onArticleMouseEnter(articleIdx) {
        this.state.selectedIdx = articleIdx;
    }

    onCreateClick() {
        this.props.create(this.searchInput.el.value);
        this.props.close();
    }

    async onSearchInput(ev) {
        await this.debouncedSearch(ev.target.value);
        this.state.displayEmptySearch = true;
    }

    onWindowPointerUp(ev) {
        const container = closestScrollableY(this.root.el) ?? this.root.el;
        if (!container.contains(ev.target)) {
            this.props.close();
        }
    }

    openSelectedArticle() {
        if (this.state.articles.length > this.state.selectedIdx) {
            this.props.select(this.state.articles[this.state.selectedIdx]);
        }
        this.props.close();
    }

    async search(searchValue) {
        if (!searchValue.length && !this.props.searchEmptyQuery) {
            this.state.articles = [];
        } else {
            this.state.articles = (await this.props.search(searchValue)).map((article) => ({
                displayName: `${article.icon || "📄"} ${article.name}`.trim(),
                headline: article.headline ? markup(article.headline) : "",
                icon: article.icon || "📄",
                id: article.id,
                isFavorite: article.is_user_favorite,
                text:
                    article.name &&
                    highlightText(searchValue, article.name, "fw-bolder text-primary"),
                subjectText:
                    article.root_article_id?.[0] &&
                    article.root_article_id[0] != article.id &&
                    highlightText(
                        searchValue,
                        article.root_article_id[1],
                        "fw-bolder text-primary"
                    ),
            }));
        }
        this.state.selectedIdx = 0;
    }
}
