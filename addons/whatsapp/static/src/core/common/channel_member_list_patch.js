import { ChannelMemberList } from "@mail/discuss/core/common/channel_member_list";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Thread} */
const channelMemberListPatch = {
    canOpenChatWith(member) {
        return (
            super.canOpenChatWith(member) &&
            member.partner_id.notEq(member.channel_id.whatsapp_partner_id)
        );
    },
};

patch(ChannelMemberList.prototype, channelMemberListPatch);
