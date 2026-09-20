import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

import { rpc } from "@web/core/network/rpc";
import { KeepLast } from "@web/core/utils/concurrency";

export class KnowledgeBaseAutocomplete extends Interaction {
    static selector = ".o_helpdesk_knowledge_search";
    dynamicContent = {
        _root: {
            "t-on-focusout": this.debounced(this.onFocusout, 100),
            "t-att-class": () => ({
                "dropdown": this.hasResults,
                "show": this.hasResults,
            })
        },
        ".search-query": {
            "t-on-input": this.debounced(this.onInput, 400),
            "t-on-keydown": this.onKeydown,
        },
    };

    setup() {
        this.inputEl = this.el.querySelector(".search-query");
        this.searchGroupEl = this.el.querySelector(".input-group");
        this.enabled = parseInt(this.el.dataset.autocomplete);
        this.hasResults = false;
        this.keepLast = new KeepLast();
        this.url = this.el.dataset.acUrl;
    }

    async fetch() {
        const search = this.inputEl.value;
        if (!search || search.length < 3) {
            return;
        }
        return await rpc(this.url, { "term": search });
    }

    /**
     * @param {Object} result 
     */
    render(result) {
        this.hasResults = !!result;
        const prevMenuEl = this.menuEl?.[0];
        if (this.hasResults) {
            this.menuEl = this.renderAt("website_helpdesk.knowledge_base_autocomplete", {
                results: result.results,
                showMore: result.showMore,
                term: this.inputEl.value,
            });
            this.searchGroupEl.dataset.bsToggle = "dropdown";
        }
        if (prevMenuEl) {
            prevMenuEl.remove();
        }
    }

    onFocusout() {
        if (!this.el.contains(document.activeElement)) {
            this.render();
        }
    }

    async onInput() {
        if (!this.enabled) {
            return;
        }
        const result = await this.keepLast.add(this.waitFor(this.fetch()));
        this.render(result);
    }

    /**
     * @param {KeyboardEvent} ev 
     */
    onKeydown(ev) {
        switch (ev.key) {
            case "Escape":
                this.render();
                break;
            case "ArrowUp":
            case "ArrowDown":
                ev.preventDefault();
                if (this.menuEl) {
                    const newFocusEl =
                        ev.key === "ArrowUp"
                            ? this.menuEl[0].lastElementChild
                            : this.menuEl[0].firstElementChild;
                    newFocusEl.focus();
                }
                break;
        }
    }
}

registry
    .category("public.interactions")
    .add("website_helpdesk.knowledge_base_autocomplete", KnowledgeBaseAutocomplete);
