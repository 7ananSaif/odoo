import { Composer } from "@mail/core/common/composer";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

// TODO ABD: could be replaced by a KnowledgeComposer ?
/** @type {Composer} */
const composerPatch = {
    get hasGifPicker() {
        // Done to remove the gif picker when in Knowledge as per the specs
        return super.hasGifPicker && !this.env.inKnowledge;
    },
    /**
     * Change the label on the button that posts comments on an article.
     * @override
     **/
    get SEND_TEXT() {
        return this.props.composer?.thread?.model === "knowledge.article.thread"
            ? _t("Post")
            : super.SEND_TEXT;
    },
};
patch(Composer.prototype, composerPatch);
