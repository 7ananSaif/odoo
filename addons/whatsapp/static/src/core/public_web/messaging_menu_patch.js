import { MessagingMenu } from "@mail/core/public_web/messaging_menu";
import { ThreadIcon } from "@mail/core/common/thread_icon";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(MessagingMenu, {
    components: { ...MessagingMenu.components, ThreadIcon },
});

patch(MessagingMenu.prototype, {
    get _tabs() {
        const items = super._tabs;
        const hasWhatsApp = Object.values(this.store.Thread.records).some(
            ({ channel_type }) => channel_type === "whatsapp"
        );
        if (hasWhatsApp) {
            items.push({
                counter: this.store.discuss.whatsapp.threadsWithCounter.length,
                icon: "fa fa-whatsapp",
                id: "whatsapp",
                label: _t("WhatsApp"),
                sequence: 80,
            });
        }
        return items;
    },
});
