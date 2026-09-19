import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { DocumentsControllerMixin } from "@documents/views/documents_controller_mixin";
import { preSuperSetup, useDocumentView } from "@documents/views/hooks";
import { DocumentsSelectionBox } from "@documents/views/selection_box/documents_selection_box";
import { onWillRender, useEffect, useRef, useState } from "@odoo/owl";

export class DocumentsListController extends DocumentsControllerMixin(ListController) {
    static template = "documents.DocumentsListController";
    static components = {
        ...ListController.components,
        Dropdown,
        SelectionBox: DocumentsSelectionBox,
    };
    setup() {
        preSuperSetup();
        super.setup(...arguments);
        this.documentService = useService("document.document");
        this.uploadFileInputRef = useRef("uploadFileInput");
        const properties = useDocumentView(this.documentsViewHelpers());
        Object.assign(this, properties);

        this.documentStates = useState({
            previewStore: {},
        });
        this.rightPanelState = useState(this.documentService.rightPanelReactive);

        if (!this.documentService.userIsInternal) {
            this.archInfo.columns = this.archInfo.columns.filter(
                (col) => !this.internalOnlyColumns.includes(col.name)
            );
        }

        useEffect(
            () => {
                this.documentService.getSelectionActions = () => ({
                    getTopbarActions: () => this.getTopBarActionMenuItems(),
                    getMenuProps: () => this.actionMenuProps,
                });
            },
            () => []
        );

        onWillRender(() => this.openInitialPreview());
    }

    get hasSelectedRecords() {
        return this.targetRecords.length;
    }

    get targetRecords() {
        return this.model.targetRecords;
    }

    get internalOnlyColumns() {
        return ["company_id"];
    }

    /**
     * Override this to add view options.
     */
    documentsViewHelpers() {
        return {
            getSelectedDocumentsElements: () =>
                this.root?.el?.querySelectorAll(
                    ".o_data_row.o_data_row_selected .o_list_record_selector"
                ) || [],
            setPreviewStore: (previewStore) => {
                this.documentStates.previewStore = previewStore;
            },
            isRecordPreviewable: this.isRecordPreviewable.bind(this),
        };
    }

    isRecordPreviewable(record) {
        return record.isViewable();
    }
}
