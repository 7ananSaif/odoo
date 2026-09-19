import { patch } from "@web/core/utils/patch";
import { DocumentsListActionItemDownload } from "@documents/views/list/action_widget/documents_list_action_item_download";

patch(DocumentsListActionItemDownload.prototype, {

    get isVisible() {
        return super.isVisible && this.props.record.data.handler !== "spreadsheet";
    }

});
