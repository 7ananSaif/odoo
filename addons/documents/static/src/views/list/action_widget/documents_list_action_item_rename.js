import { _t } from "@web/core/l10n/translation";

import { DocumentsListActionItem } from "./documents_list_action_item";

export class DocumentsListActionItemRename extends DocumentsListActionItem {
    setup() {
        super.setup();
        this.icon = "fa-edit";
        this.description = _t("Rename");
    }

    get isVisible() {
        return this.props.record.isActive && this.documentService.isEditable(this.props.record.data);
    }

    async onActionClicked() {
        await this.documentService.openDialogRename(this.props.record.data.id);
        await this.env.model._notifyChange();
    }
}
