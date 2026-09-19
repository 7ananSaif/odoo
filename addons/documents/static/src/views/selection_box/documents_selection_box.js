import { SelectionBox } from "@web/views/view_components/selection_box";

export class DocumentsSelectionBox extends SelectionBox {
    onUnselectAll() {
        super.onUnselectAll();
        this.props.root.model.documentService.bus.trigger("UPDATE-DOCUMENT-FOLDER");
    }
}
