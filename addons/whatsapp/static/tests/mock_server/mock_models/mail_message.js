import { mailModels } from "@mail/../tests/mail_test_helpers";

import { getKwArgs } from "@web/../tests/web_test_helpers";

export class MailMessage extends mailModels.MailMessage {
    /**
     * @override
     * @type {typeof mailModels.MailMessage["prototype"]["_to_store"]}
     */
    _to_store(store, fields, for_current_user, follower_by_message_partner) {
        const kwargs = getKwArgs(
            arguments,
            "store",
            "fields",
            "for_current_user",
            "follower_by_message_partner"
        );
        store = kwargs.store;

        /** @type {import("mock_models").WhatsAppMessage} */
        const WhatsAppMessage = this.env["whatsapp.message"];

        super._to_store(...arguments);
        for (const message of this) {
            const [whatsappMessage] = WhatsAppMessage.search_read([
                ["mail_message_id", "=", message.id],
            ]);
            if (whatsappMessage) {
                store._add_record_fields(this.browse(message.id), {
                    whatsappStatus: whatsappMessage.state,
                });
            }
        }
    }
}
