import {
    HtmlComposerMessageField,
    htmlComposerMessageField,
} from "@mail/views/web/fields/html_composer_message_field/html_composer_message_field";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { markup } from "@odoo/owl";

export class DocumentsHtmlComposerMessageField extends HtmlComposerMessageField {
    setup() {
        super.setup();
        if (this.env.model.bus) {
            useBus(this.env.model.bus, "PASTE_SHARE_LINKS", (ev) => {
                this.editor.shared.dom.insert(this.formatLinks(ev.detail.links));
                this.editor.editable.focus();
                this.editor.shared.history.addStep();
            });
        }
    }

    /**
     * Formats the links to valid HTML so to paste the links to the `body` (html) field.
     * @param {Array} response - The response containing document details.
     */
    formatLinks(response) {
        const html = response
            .map(
                ({ display_name, access_url }) =>
                    markup`<a href="${access_url}" target="_blank" class="d-block">${display_name}</a>`
            )
        const cleanHTML = markup(Array(html.length + 1).fill(""), ...html);
        const root = document.createElement("div");
        root.innerHTML = cleanHTML;
        return root;
    }
}

export const documentsHtmlComposerMessageField = {
    ...htmlComposerMessageField,
    component: DocumentsHtmlComposerMessageField,
};

registry
    .category("fields")
    .add("documents_html_composer_message", documentsHtmlComposerMessageField);
