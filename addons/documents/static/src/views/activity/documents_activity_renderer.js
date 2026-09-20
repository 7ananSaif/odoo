import { ActivityRenderer } from "@mail/views/web/activity/activity_renderer";

import { DocumentsRightPanel } from "@documents/components/documents_right_panel/documents_right_panel";
import { DocumentsRendererMixin } from "@documents/views/documents_renderer_mixin";
import { DocumentsFileViewer } from "@documents/views/helper/documents_file_viewer";

import { onWillUpdateProps, useRef } from "@odoo/owl";

export class DocumentsActivityRenderer extends DocumentsRendererMixin(ActivityRenderer) {
    static props = {
        ...ActivityRenderer.props,
        previewStore: Object,
    };
    static template = "documents.DocumentsActivityRenderer";
    static components = {
        ...ActivityRenderer.components,
        DocumentsRightPanel,
        DocumentsFileViewer,
    };

    setup() {
        super.setup();
        this.root = useRef("root");

        onWillUpdateProps((nextProps) => {
            const selectedRecord = nextProps.records.find((r) => r.selected);
            if (selectedRecord) {
                this.documentService.focusRecord(selectedRecord);
            }
        });
    }

    getDocumentsAttachmentViewerProps() {
        return { previewStore: this.props.previewStore };
    }
}
