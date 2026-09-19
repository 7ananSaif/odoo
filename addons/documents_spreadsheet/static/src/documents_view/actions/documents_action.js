import { patch } from "@web/core/utils/patch";
import { DocumentsAction } from "@documents/views/action/documents_action";

patch(DocumentsAction.prototype, {
    isPreviewAction(action) {
        return super.isPreviewAction(action) && action.key !== "insert";
    },
});
