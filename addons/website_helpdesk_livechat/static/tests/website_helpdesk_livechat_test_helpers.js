import { helpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";

import { livechatModels } from "@im_livechat/../tests/livechat_test_helpers";

import { mailModels } from "@mail/../tests/mail_test_helpers";

import { ResUsers } from "@website_helpdesk_livechat/../tests/mock_server/models/res_users";

import { defineModels } from "@web/../tests/web_test_helpers";

export const websiteHelpdeskLivechatModels = {
    ...helpdeskModels,
    ...mailModels,
    ...livechatModels,
    ResUsers,
};

export function defineWebsiteHelpdeskLivechatModels() {
    return defineModels(websiteHelpdeskLivechatModels);
}
