import { _t } from "@web/core/l10n/translation";

import { DocumentsListActionItem } from "./documents_list_action_item";

export class DocumentsListActionItemDownload extends DocumentsListActionItem {
    setup() {
        super.setup();
        this.icon = "fa-download";
        this.description = _t("Download");
    }

    get isVisible() {
        return this.props.record.data.type !== "binary" || this.props.record.data.attachment_id;
    }

    async onActionClicked() {
        await this.documentService.downloadDocuments([this.props.record])
    }
}
