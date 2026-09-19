import { STATIC_COG_GROUP_ACTION_CLEANUP } from "./documents_cog_menu_group";
import { DocumentsCogMenuItem } from "./documents_cog_menu_item";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemArchive extends DocumentsCogMenuItem {
    setup() {
        this.icon = "fa-trash";
        this.label = _t("Move to trash");
        this.documentService = useService("document.document");
        super.setup();
    }

    async doActionOnFolder(folder) {
        await this.documentService.moveToTrash(folder.id);
        await this.reload();
    }
}

export const documentsCogMenuItemArchive = {
    Component: DocumentsCogMenuItemArchive,
    groupNumber: STATIC_COG_GROUP_ACTION_CLEANUP,
    isDisplayed: (env) =>
        DocumentsCogMenuItem.isVisible(
            env,
            ({ folder, documentService }) =>
                documentService.userIsInternal && documentService.isEditable(folder)
        ),
};
