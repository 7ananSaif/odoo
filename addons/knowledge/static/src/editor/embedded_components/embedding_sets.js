import { macrosClipboardEmbedding } from "@knowledge/editor/embedded_components/backend/clipboard/macros_embedded_clipboard";
import { macrosFileEmbedding } from "@knowledge/editor/embedded_components/backend/file/macros_file";
import { readonlyMacrosFileEmbedding } from "@knowledge/editor/embedded_components/backend/file/readonly_macros_file";
import { articleIndexEmbedding } from "@knowledge/editor/embedded_components/backend/article_index/article_index";
import { readonlyArticleIndexEmbedding } from "@knowledge/editor/embedded_components/core/article_index/readonly_article_index";
import { readonlyViewEmbedding } from "@knowledge/editor/embedded_components/backend/view/readonly_embedded_view";
import { viewEmbedding } from "@knowledge/editor/embedded_components/backend/view/embedded_view";
import { readonlyViewLinkEmbedding } from "@knowledge/editor/embedded_components/backend/embedded_view_link/readonly_embedded_view_link";
import { viewLinkEmbedding } from "@knowledge/editor/embedded_components/backend/embedded_view_link/embedded_view_link";
import { foldableSectionEmbedding } from "@knowledge/editor/embedded_components/backend/foldable_section/foldable_section";
import { readonlyFoldableSectionEmbedding } from "@knowledge/editor/embedded_components/core/readonly_foldable_section/readonly_foldable_section";

export const KNOWLEDGE_EMBEDDINGS = [
    articleIndexEmbedding,
    foldableSectionEmbedding,
    macrosClipboardEmbedding,
    macrosFileEmbedding,
    viewEmbedding,
    viewLinkEmbedding,
];

export const KNOWLEDGE_READONLY_EMBEDDINGS = [
    macrosClipboardEmbedding,
    readonlyArticleIndexEmbedding,
    readonlyFoldableSectionEmbedding,
    readonlyMacrosFileEmbedding,
    readonlyViewEmbedding,
    readonlyViewLinkEmbedding,
];
