import { readonlyArticleIndexEmbedding } from "@knowledge/editor/embedded_components/core/article_index/readonly_article_index";
import { clipboardEmbedding } from "@knowledge/editor/embedded_components/core/clipboard/embedded_clipboard";
import { readonlyFoldableSectionEmbedding } from "@knowledge/editor/embedded_components/core/readonly_foldable_section/readonly_foldable_section";
import { viewPlaceholderEmbedding } from "@website_knowledge/frontend/editor/embedded_components/view/view_placeholder";
import { publicViewLinkEmbedding } from "@website_knowledge/frontend/editor/embedded_components/view_link/public_embedded_view_link";

export const KNOWLEDGE_PUBLIC_EMBEDDINGS = [
    clipboardEmbedding,
    publicViewLinkEmbedding,
    readonlyArticleIndexEmbedding,
    readonlyFoldableSectionEmbedding,
    viewPlaceholderEmbedding,
];
