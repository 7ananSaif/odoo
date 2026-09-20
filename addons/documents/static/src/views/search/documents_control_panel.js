import { DocumentsAction } from "@documents/views/action/documents_action";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { DocumentsBreadcrumbs } from "@documents/components/documents_breadcrumbs";
import { DocumentsCogMenu } from "../cog_menu/documents_cog_menu";
import { onPatched, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentsControlPanel extends ControlPanel {
    static template = "documents.ControlPanel";
    static components = {
        ...ControlPanel.components,
        DocumentsBreadcrumbs,
        DocumentsCogMenu,
        DocumentsAction,
    };

    setup() {
        super.setup();
        this.documentService = useService("document.document");

        this.rightPanelState = useState(this.documentService.rightPanelReactive);

        onPatched(() => {
            const searchPanelContainer = document.querySelector('.o_search_panel');
            if (searchPanelContainer) {
                searchPanelContainer.classList.toggle('d-none', this.env.isSmall && this.env.model.root.selection.length);
            }
        });
    }

    /**
     * Return the current folder ID.
     */
    get currentFolderId() {
        return this.env.searchModel.getSelectedFolderId();
    }

    get showActions() {
        const previewing = !!this.rightPanelState.previewedDocument;
        const focusing = !!this.rightPanelState.focusedRecord;
        const focusedSelected =
            focusing &&
            !!this.env.model.root.selection.find(
                (r) => r.id === this.rightPanelState.focusedRecord.id
            );
        return (
            this.env.config.viewType != "activity" && !previewing && (!focusing || focusedSelected)
        );
    }

    get pathBreadcrumbs() {
        // users come from another app
        if (this.env.model.config.context.active_model) {
            return [
                ...this.env.config.breadcrumbs.slice(0, -1),
                {
                    name: this.env.searchModel.getSelectedFolder().display_name,
                },
            ];
        }

        return this.env.searchModel.getSelectedFolderAndParents().reverse().map(folder => {
            return {
                jsId: folder.id,
                name: folder.display_name,
                onSelected: () => {
                    const folderSection = this.env.searchModel.getSections()[0];
                    this.env.searchModel.toggleCategoryValue(folderSection.id, folder.id);
                }
            }
        });
    }
}
