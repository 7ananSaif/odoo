import { Message } from "@mail/core/common/message_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Message} */
const messagePatch = {
    get editable() {
        if (this.thread?.channel_type === "whatsapp") {
            return false;
        }
        return super.editable;
    },
    /** @override */
    canReplyTo(thread) {
        return super.canReplyTo(thread) && !this.thread?.composer?.threadExpired;
    },
    isTranslatable(thread) {
        return (
            super.isTranslatable(thread) ||
            (this.store.hasMessageTranslationFeature &&
                thread?.channel_type === "whatsapp" &&
                this.store.self?.main_user_id?.share === false)
        );
    },
};
patch(Message.prototype, messagePatch);
