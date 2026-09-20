import { Attachment } from "@mail/core/common/attachment_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Attachment} */
const attachmentPatch = {
    get isViewable() {
        return super.isViewable || this.mimetype === "application/o-spreadsheet";
    },
};
patch(Attachment.prototype, attachmentPatch);
