import { AttachmentUploader } from "@mail/core/common/attachment_uploader_hook";
import { patch } from "@web/core/utils/patch";

patch(AttachmentUploader.prototype, {
    /**
     * @override
     */
    async uploadFile() {
        if (!this.thread.id && this.thread.model === "knowledge.article.thread") {
            this.thread = await this.thread.store.env.services["knowledge.comments"].createThread();
            this.composer = this.thread.composer;
            const commentsState =
                this.thread.store.env.services["knowledge.comments"].getCommentsState();
            commentsState.shouldOpenActiveThread = true;
            commentsState.activeThreadId = this.thread.id.toString();
        }
        return super.uploadFile(...arguments);
    },
});
