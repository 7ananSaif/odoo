import { ComposerAction, registerComposerAction } from "@mail/core/common/composer_actions";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

registerComposerAction("revive-whatsapp-conversation", {
    condition: ({ composer, owner }) =>
        composer.thread?.channel_type === "whatsapp" && !owner.state.active,
    icon: "fa fa-whatsapp",
    name: _t("Revive WhatsApp Conversation"),
    onSelected: ({ owner }) => owner.onclickWhatsAppChat(),
    sequenceQuick: 10,
});

patch(ComposerAction.prototype, {
    _condition({ composer, owner }) {
        if (
            ["upload-files", "voice-start"].includes(this.id) &&
            composer.targetThread?.channel_type === "whatsapp" &&
            (composer.attachments.length > 0 || owner.voiceRecorder?.recording)
        ) {
            return false;
        }
        return super._condition(...arguments);
    },
    _disabledCondition({ composer, owner }) {
        const inactiveActions = ["revive-whatsapp-conversation", "more-actions"];
        if (
            composer.targetThread?.channel_type === "whatsapp" &&
            owner.state &&
            !owner.state.active &&
            !inactiveActions.includes(this.id)
        ) {
            return true;
        }
        return super._disabledCondition(...arguments);
    },
});
