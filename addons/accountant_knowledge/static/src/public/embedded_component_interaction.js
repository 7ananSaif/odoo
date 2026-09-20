import {
    EmbeddedComponentInteraction,
    getEmbeddingMap,
} from "@html_editor/public/embedded_components/embedded_component_interaction";
import { patch } from "@web/core/utils/patch";
import { ACCOUNTANT_KNOWLEDGE_PUBLIC_EMBEDDINGS } from "@accountant_knowledge/public/embedding_sets";

/**
 * TODO ABD:
 * This patch should really be in a accountant_website_knowledge module, since
 * it relies on `knowledgePublicViewEl`, but it should and will do nothing when
 * that variable is not set, so this patch will stay here until that module
 * has a greater reason for existence.
 */
patch(EmbeddedComponentInteraction.prototype, {
    getEmbedding(name) {
        let embedding;
        if (this.knowledgePublicViewEl) {
            // Restrict Knowledge embedded components in the Knowledge public view.
            embedding = getEmbeddingMap(ACCOUNTANT_KNOWLEDGE_PUBLIC_EMBEDDINGS).get(name);
        }
        return embedding ?? super.getEmbedding(name);
    },
});
