import { patch } from "@web/core/utils/patch";
import { KnowledgeHtmlField } from "@knowledge/components/knowledge_html_field/knowledge_html_field";
import { SignatureInputPlugin } from "@accountant_knowledge/editor/plugins/signature_input_plugin/signature_input_plugin";
import { UploadLinkPlugin } from "@accountant_knowledge/editor/plugins/upload_link_plugin/upload_link_plugin";

patch(KnowledgeHtmlField.prototype, {
    /** @override */
    getConfig() {
        const config = super.getConfig();
        // Add new plugins:
        config.Plugins.push(
            SignatureInputPlugin,
            UploadLinkPlugin,
        );
        return config;
    },
});
