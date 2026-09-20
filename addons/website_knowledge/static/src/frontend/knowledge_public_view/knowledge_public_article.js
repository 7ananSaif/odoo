import { markup } from "@odoo/owl";
import { router } from "@web/core/browser/router";
import { rpc } from "@web/core/network/rpc";
import { KeepLast } from "@web/core/utils/concurrency";
import { Reactive } from "@web/core/utils/reactive";

export class Article extends Reactive {
    constructor(id) {
        super();
        this.model = "knowledge.article";
        this.resId = id;
        this.keepLastLoad = new KeepLast();
    }

    /**
     * Load the content of a newly opened article which should replace
     * the current one. The router state and url are updated to properly handle
     * browser "next" and "previous".
     *
     * @param {Number} id
     */
    async load(id) {
        if (id) {
            router.pushState({ resId: id }, { replace: true });
        } else {
            id = this.resId;
        }
        const result = await this.keepLastLoad.add(
            rpc(`/knowledge/public/article`, { article_id: id })
        );
        this.resId = id;
        this.content = markup(result.content);
    }
}
