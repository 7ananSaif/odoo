import { livechatModels } from "@im_livechat/../tests/livechat_test_helpers";

import { serverState } from "@web/../tests/web_test_helpers";

export class ResUsers extends livechatModels.ResUsers {
    _init_store_data(store) {
        super._init_store_data(...arguments);
        store.add({
            helpdesk_livechat_active: true,
            has_access_create_ticket: this.env.user?.group_ids.includes(
                serverState.groupHelpdeskId
            ),
        });
    }
}
