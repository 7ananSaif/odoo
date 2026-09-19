import { Attachment } from "@mail/core/common/attachment_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Attachment} */
const attachmentPatch = {
    get isPdf() {
        if (this.documentData && this.documentData.has_embedded_pdf) {
            return true;
        }
        return super.isPdf;
    },
};
patch(Attachment.prototype, attachmentPatch);
