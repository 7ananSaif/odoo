import { registerComposerAction } from "@mail/core/common/composer_actions";
import { _t } from "@web/core/l10n/translation";

import { SelectAddDocumentCreateDialog } from "@documents/views/view_dialogs/select_add_document_create_dialog";

registerComposerAction("add-documents", {
    icon: { template: "documents.DocumentsIcon" },
    name: _t("Add from Documents"),
    onSelected: ({ composer, store }) => {
        const thread = composer?.message?.thread || composer.targetThread;
        store.env.services.dialog.add(SelectAddDocumentCreateDialog, {
            resModel: "documents.document",
            title: _t("Search: Documents"),
            noCreate: true,
            domain: [
                ["type", "=", "binary"],
                ["shortcut_document_id", "=", false],
            ],
            context: {
                list_view_ref: "documents.documents_view_list_add_documents_attachment",
                documents_search_panel_no_trash: true,
                documents_view_secondary: true,
            },
            chatterParams: {
                thread,
                composer,
            },
        });
    },
    sequence: 10,
});
