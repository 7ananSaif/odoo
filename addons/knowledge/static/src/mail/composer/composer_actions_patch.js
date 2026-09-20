import { ComposerAction } from "@mail/core/common/composer_actions";
import { patch } from "@web/core/utils/patch";

patch(ComposerAction.prototype, {
    _condition({ owner }) {
        // Hide composer actions that are not needed in the Knowledge comment UI.
        if (["send-message", "add-gif", "add-canned-response"].includes(this.id) && owner.env.inKnowledge) {
            return false;
        }
        return super._condition(...arguments);
    },
});
