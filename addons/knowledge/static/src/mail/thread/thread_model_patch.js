import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    /** @type {boolean|undefined} */
    knowledgePreLoading: undefined,
    /** @type {number|undefined} */
    articleId: undefined,

    /**
     * @override
     */
    async fetchMessagesData({ after, around, before }) {
        if (!this.knowledgePreLoading) {
            return await super.fetchMessagesData(...arguments);
        } else {
            return await this.store.env.services["knowledge.comments"].fetchMessages(this.id);
        }
    },
    /** @override */
    open() {
        if (this.model !== "knowledge.article.thread") {
            return super.open(...arguments);
        }
        this.store.env.services.orm
            .read("knowledge.article.thread", [this.id], ["article_id"], { load: false })
            .then(([articleThreadData]) => {
                this.store.env.services.action.doAction(
                    "knowledge.ir_actions_server_knowledge_home_page",
                    {
                        stackPosition: "replaceCurrentAction",
                        additionalContext: {
                            res_id: articleThreadData["article_id"],
                        },
                    }
                );
            });
        return true;
    },
});
