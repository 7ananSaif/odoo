import { registerThreadAction } from "@mail/core/common/thread_actions";

import { _t } from "@web/core/l10n/translation";

registerThreadAction("view-contact", {
    condition: ({ owner, thread }) =>
        thread?.channel_type === "whatsapp" &&
        thread.whatsapp_partner_id &&
        !owner.isDiscussSidebarChannelActions,
    open: ({ store, thread }) => {
        if (store.env.isSmall) {
            store?.ChatWindow.get({ thread }).fold();
        } else {
            thread.openChatWindow({ focus: true });
        }
        store.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            res_id: thread.whatsapp_partner_id.id,
        });
    },
    icon: "fa fa-fw fa-address-book",
    name: _t("View Contact"),
    sequenceGroup: 1,
});
