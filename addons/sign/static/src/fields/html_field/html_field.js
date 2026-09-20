import { HtmlField } from "@html_editor/fields/html_field";
import { SignaturePlugin } from "@sign/editor/plugins/signature";
import { patch } from "@web/core/utils/patch";

patch(HtmlField.prototype, {
    /** @override */
    getConfig() {
        const config = super.getConfig();
        config.Plugins.push(SignaturePlugin);
        return config;
    },
});
