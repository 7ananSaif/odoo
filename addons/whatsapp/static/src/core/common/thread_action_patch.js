import { patch } from "@web/core/utils/patch";
import { ThreadAction } from "@mail/core/common/thread_actions";

patch(ThreadAction.prototype, {
    _condition({ action, owner, store, thread }) {
        if (thread?.channel_type === "whatsapp") {
            if (
                action.id === "create-lead" &&
                store.has_access_create_lead &&
                !owner.isDiscussSidebarChannelActions
            ) {
                return true;
            }
            if (
                action.id === "create-ticket" &&
                store.has_access_create_ticket &&
                store.helpdesk_livechat_active &&
                !action.isDiscussSidebarChannelActions
            ) {
                return true;
            }
        }
        return super._condition(...arguments);
    },
});
