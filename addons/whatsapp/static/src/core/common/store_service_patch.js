import { Store } from "@mail/core/common/store_service";
import { patch } from "@web/core/utils/patch";

patch(Store.prototype, {
    async getMessagePostParams({ thread }) {
        const params = await super.getMessagePostParams(...arguments);

        if (thread.channel_type === "whatsapp") {
            params.post_data.message_type = "whatsapp_message";
        }
        return params;
    },
});
