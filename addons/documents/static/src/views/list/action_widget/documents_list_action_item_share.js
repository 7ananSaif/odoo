import { _t } from "@web/core/l10n/translation";

import { DocumentsListActionItem } from "./documents_list_action_item";

export class DocumentsListActionItemShare extends DocumentsListActionItem {
    setup() {
        super.setup();
        this.icon = "fa-user-plus";
        this.description = _t("Share");
    }

    get isVisible() {
        return (
            this.props.record.isActive &&
            this.documentService.userIsInternal &&
            this.documentService.isFolderSharable(this.props.record.data)
        );
    }

    async onActionClicked() {
        await this.documentService.openSharingDialog([this.props.record.data.id])
    }
}
