import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";
import { ResUsers } from "@documents/../tests/mock_server/mock_models/res_users";

export function defineDocumentsModels() {
    return defineModels(documentsModels);
}

export const documentsModels = { ...mailModels, ResUsers };
