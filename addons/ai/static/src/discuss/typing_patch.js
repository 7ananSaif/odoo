import { patch } from "@web/core/utils/patch";
import { Typing } from "@mail/discuss/typing/common/typing";
import { _t } from "@web/core/l10n/translation";

patch(Typing.prototype, {
    get text() {
        const channel = this.props.channel;
        const typingMembers = channel?.typingMembers || [];
        if (typingMembers.length === 1 && typingMembers[0].partner_id?.im_status === "agent") {
            return _t("AI is thinking...");
        }
        return super.text;
    },
});
