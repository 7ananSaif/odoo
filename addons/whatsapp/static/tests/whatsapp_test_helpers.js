import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";

import { DiscussChannel } from "./mock_server/mock_models/discuss_channel";
import { MailMessage } from "./mock_server/mock_models/mail_message";
import { MailThread } from "./mock_server/mock_models/mail_thread";
import { ResUsersSettings } from "./mock_server/mock_models/res_users_settings";
import { WhatsAppAccount } from "./mock_server/mock_models/whatsapp_account";
import { WhatsAppComposer } from "./mock_server/mock_models/whatsapp_composer";
import { WhatsAppMessage } from "./mock_server/mock_models/whatsapp_message";
import { WhatsAppTemplate } from "./mock_server/mock_models/whatsapp_template";

export function defineWhatsAppModels() {
    return defineModels(whatsAppModels);
}

export const whatsAppModels = {
    ...mailModels,
    DiscussChannel,
    MailMessage,
    MailThread,
    ResUsersSettings,
    WhatsAppAccount,
    WhatsAppComposer,
    WhatsAppMessage,
    WhatsAppTemplate,
};
