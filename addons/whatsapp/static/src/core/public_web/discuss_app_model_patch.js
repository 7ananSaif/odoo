import { fields } from "@mail/core/common/record";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup(env) {
        super.setup(...arguments);
        this.whatsapp = fields.One("DiscussAppCategory", {
            compute() {
                return {
                    addTitle: _t("Search WhatsApp Channel"),
                    extraClass: "o-mail-DiscussSidebarCategory-whatsapp",
                    hideWhenEmpty: true,
                    icon: "fa fa-whatsapp",
                    id: "whatsapp",
                    name: _t("WhatsApp"),
                    sequence: 20,
                    serverStateKey: "is_discuss_sidebar_category_whatsapp_open",
                };
            },
            eager: true,
        });
    },
});
