import { DocumentsChatter } from "@documents/views/chatter/documents_chatter";
import { useService } from "@web/core/utils/hooks";

import { DocumentsDetailsPanel } from "@documents/components/documents_details_panel/documents_details_panel";

import { Component, useState } from "@odoo/owl";

export class DocumentsRightPanel extends Component {
    static template = "documents.DocumentsViews.RightPanel";
    static props = {
        nbViewItems: { type: Number },
    };
    static components = {
        Chatter: DocumentsChatter,
        DocumentsDetailsPanel,
    };

    setup() {
        this.documentService = useService("document.document");
        this.state = useState(this.documentService.rightPanelReactive);
    }

    get panelDisabled() {
        return (
            !this.state.focusedRecord ||
            !this.state.focusedRecord.data ||
            typeof this.state.focusedRecord.data.id !== "number"
        );
    }
}
