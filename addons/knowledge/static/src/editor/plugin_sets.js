import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { AutofocusPlugin } from "@knowledge/editor/plugins/autofocus_plugin/autofocus_plugin";
import { KnowledgeArticlePlugin } from "@knowledge/editor/plugins/article_plugin/article_plugin";
import { KnowledgeCommentsPlugin } from "@knowledge/editor/plugins/comments_plugin/comments_plugin";
import { KnowledgeDeleteFirstLinePlugin } from "@knowledge/editor/plugins/delete_first_line_plugin/delete_first_line_plugin";
import { ArticleIndexPlugin } from "@knowledge/editor/embedded_components/plugins/article_index_plugin/article_index_plugin";
import { EmbeddedClipboardPlugin } from "@knowledge/editor/embedded_components/plugins/embedded_clipboard_plugin/embedded_clipboard_plugin";
import { EmbeddedViewPlugin } from "@knowledge/editor/embedded_components/plugins/embedded_view_plugin/embedded_view_plugin";
import { FoldableSectionPlugin } from "@knowledge/editor/embedded_components/plugins/foldable_section_plugin/foldable_section_plugin";
import { InsertPendingElementPlugin } from "@knowledge/editor/plugins/insert_pending_element_plugin/insert_pending_element_plugin";
import { HeadingLinkPlugin } from "@knowledge/editor/plugins/heading_link_plugin/heading_link_plugin";

MAIN_PLUGINS.push(KnowledgeArticlePlugin);

export const KNOWLEDGE_PLUGINS = [
    AutofocusPlugin,
    InsertPendingElementPlugin,
    KnowledgeCommentsPlugin,
    KnowledgeDeleteFirstLinePlugin,
    HeadingLinkPlugin,
];

export const KNOWLEDGE_EMBEDDED_COMPONENT_PLUGINS = [
    ArticleIndexPlugin,
    EmbeddedClipboardPlugin,
    EmbeddedViewPlugin,
    FoldableSectionPlugin,
];
