import { _t } from "@web/core/l10n/translation";

import { DocumentsListActionItem } from "./documents_list_action_item";

export class DocumentsListActionItemDetails extends DocumentsListActionItem {
    setup() {
        super.setup();
        this.icon = "fa-info-circle";
        this.description = _t("Details");
    }

    get isVisible() {
        return this.documentService.userIsInternal;
    }

    async onActionClicked() {
        if (this.documentService.focusedRecord.id != this.props.record.id) {
            this.documentService.focusRecord(this.props.record);
            this.documentService.rightPanelReactive.visible ||
                this.documentService.toggleRightPanelVisibility();
        } else {
            this.documentService.toggleRightPanelVisibility();
        }
    }
}
