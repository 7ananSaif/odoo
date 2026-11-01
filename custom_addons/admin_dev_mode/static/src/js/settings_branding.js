import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

/**
 * Expose the deployment's public URL to the "About" block of General Settings.
 *
 * That block is the Owl component registered as the view widget
 * "res_config_edition". Its template (see static/src/xml/settings_branding.xml)
 * links the copyright line to `baseUrl` instead of odoo.com. The value is
 * BASE_URL, injected into the session payload by models/ir_http.py.
 *
 * The component class is not exported by its own module, so it is reached
 * through the widget registry. The guard keeps a missing registration from
 * breaking the whole backend bundle.
 */
const descriptor = registry.category("view_widgets").get("res_config_edition", null);

if (descriptor?.component) {
    patch(descriptor.component.prototype, {
        setup() {
            super.setup();
            this.baseUrl = session.base_url || "/";
        },
    });
}
