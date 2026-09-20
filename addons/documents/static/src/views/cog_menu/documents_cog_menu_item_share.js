import { STATIC_COG_GROUP_ACTION_ADVANCED } from "./documents_cog_menu_group";
import { DocumentsCogMenuItem } from "./documents_cog_menu_item";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemShare extends DocumentsCogMenuItem {
    setup() {
        this.icon = "fa-share-alt";
        this.label = _t("Share");
        super.setup();
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.openSharingDialog([folder.id]);
    }
}

export const documentsCogMenuItemShare = {
    Component: DocumentsCogMenuItemShare,
    groupNumber: STATIC_COG_GROUP_ACTION_ADVANCED,
    isDisplayed: (env) =>
        DocumentsCogMenuItem.isVisible(
            env,
            ({ folder, documentService }) =>
                documentService.userIsInternal && documentService.isFolderSharable(folder)
        ),
};
