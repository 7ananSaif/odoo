import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { getCurrentViewInfo } from "@ai/discuss/core/common/view_details";
import { session } from "@web/session";

patch(Thread.prototype, {
    async post(body, postData = {}, extraData = {}) {
        const message = await super.post(body, postData, extraData);
        const aiMember = this.channel_member_ids?.find(
            (member) => member.partner_id?.im_status == "agent"
        );
        // message could be undefined if it is a command, for example /help.
        if (message?.thread?.ai_agent_id) {
            try {
                if (aiMember) {
                    aiMember.isTyping = true;
                }
                await rpc("/ai/generate_response", {
                    mail_message_id: message.id,
                    channel_id: this.id,
                    current_view_info: await getCurrentViewInfo(this.store.env.bus),
                    ai_session_identifier: session.ai_session_identifier,
                });
            } finally {
                if (aiMember) {
                    aiMember.isTyping = false;
                }
            }
        }
        return message;
    },
});
