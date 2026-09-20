import { defineModels } from "@web/../tests/web_test_helpers";
import { websiteHelpdeskLivechatModels } from "@website_helpdesk_livechat/../tests/website_helpdesk_livechat_test_helpers";

export function defineTestDiscussFullEnterpriseModels() {
    return defineModels(testDiscussFullEnterpriseModels);
}

export const testDiscussFullEnterpriseModels = {
    ...websiteHelpdeskLivechatModels,
};
