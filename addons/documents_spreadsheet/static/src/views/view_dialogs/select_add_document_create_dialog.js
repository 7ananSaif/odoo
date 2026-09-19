import { SelectAddDocumentCreateDialog } from "@documents/views/view_dialogs/select_add_document_create_dialog";
import { createXlsxAttachment } from "@documents_spreadsheet/helpers";
import { patch } from "@web/core/utils/patch";

patch(SelectAddDocumentCreateDialog.prototype, {
    
    /**
     * Convert Odoo Spreadsheet to .xlsx format
     */
    async _processAttachments(attachmentRecords) {
        return createXlsxAttachment(this.env, this.orm, attachmentRecords);
    }
});
