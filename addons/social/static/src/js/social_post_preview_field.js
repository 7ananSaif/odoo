import { SocialPostFormatterMixin } from "./social_post_formatter_mixin";

import { markup } from "@odoo/owl";

import { HtmlField, htmlField } from "@html_editor/fields/html_field";
import { registry } from "@web/core/registry";
import { createDocumentFragmentFromContent } from "@web/core/utils/html";
import { HtmlViewer } from "@html_editor/components/html_viewer/html_viewer";

class SocialHtmlViewer extends HtmlViewer {
    retargetLink() {}
}

export class FieldPostPreview extends SocialPostFormatterMixin(HtmlField) {
    static props = {
        ...FieldPostPreview.props,
        mediaType: { type: String, optional: true },
    };
    static components = {
        ...HtmlField.components,
        HtmlViewer: SocialHtmlViewer,
    };

    get value() {
        const value = this.props.record.data[this.props.name] || "";
        const html = createDocumentFragmentFromContent(value);
        for (const previewMessage of html.querySelectorAll(".o_social_preview_message")) {
            previewMessage.innerHTML = this._formatPost(previewMessage.textContent.trim());
        }
        return markup(html.body.innerHTML);
    }
}

export const fieldPostPreview = {
    ...htmlField,
    component: FieldPostPreview,
    extractProps({ attrs }) {
        const props = htmlField.extractProps(...arguments);
        props.mediaType = attrs.media_type || "";
        return props;
    },
};

registry.category("fields").add("social_post_preview", fieldPostPreview);
