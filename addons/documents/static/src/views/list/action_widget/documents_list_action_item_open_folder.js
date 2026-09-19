import { _t } from "@web/core/l10n/translation";

import { DocumentsListActionItem } from "./documents_list_action_item";

export class DocumentsListActionItemOpenFolder extends DocumentsListActionItem {
    setup() {
        super.setup();
        this.icon = "fas fa-sign-in";
        this.description = _t("Go inside");
    }

    get isVisible() {
        return this.props.record.data.type === "folder";
    }

    async onActionClicked() {
        return this.props.record.openFolder();
    }
}
