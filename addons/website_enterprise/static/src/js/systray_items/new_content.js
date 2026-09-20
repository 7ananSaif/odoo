import {
    NewContentSystrayItem,
    MODULE_STATUS,
} from "@website/client_actions/website_preview/new_content_systray_item";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(NewContentSystrayItem.prototype, {
    setup() {
        super.setup();

        this.state.newContentElements.push({
            moduleName: "website_appointment",
            moduleXmlId: "base.module_website_appointment",
            status: MODULE_STATUS.NOT_INSTALLED,
            icon: "/appointment/static/description/icon.png",
            title: _t("Appointment Form"),
            description: _t("Let visitors book meetings online"),
        });
    },
});
