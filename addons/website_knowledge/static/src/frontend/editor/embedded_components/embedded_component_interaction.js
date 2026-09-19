import {
    EmbeddedComponentInteraction,
    getEmbeddingMap,
} from "@html_editor/public/embedded_components/embedded_component_interaction";
import { patch } from "@web/core/utils/patch";
import { KNOWLEDGE_PUBLIC_EMBEDDINGS } from "@website_knowledge/frontend/editor/embedded_components/embedding_sets";

patch(EmbeddedComponentInteraction.prototype, {
    setup() {
        super.setup();
        this.knowledgePublicViewEl = this.el.closest(".o_knowledge_public_view");
    },

    getEmbedding(name) {
        let embedding;
        if (this.knowledgePublicViewEl) {
            // Restrict Knowledge embedded components in the Knowledge public view.
            embedding = getEmbeddingMap(KNOWLEDGE_PUBLIC_EMBEDDINGS).get(name);
        }
        return embedding ?? super.getEmbedding(name);
    },

    setupNewComponent({ name, env, props }) {
        super.setupNewComponent({ name, env, props });
        if (name === "view" || name === "viewLink") {
            const resId = this.el.closest(".o_knowledge_public_view")?.dataset.res_id;
            Object.assign(env, { articleId: resId ? parseInt(resId) : undefined });
        }
    },
});
