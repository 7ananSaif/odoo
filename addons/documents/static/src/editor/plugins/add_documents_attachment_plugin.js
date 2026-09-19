import { renderStaticFileBox } from "@html_editor/main/media/media_dialog/document_selector";
import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";

import { SelectAddDocumentCreateDialog } from "@documents/views/view_dialogs/select_add_document_create_dialog";

export class AddDocumentsAttachmentPlugin extends Plugin {
    static id = "add_documents_attachment";
    static dependencies = ["dom", "history", "dialog", "link", "split"];
    resources = {
        user_commands: {
            id: "addDocumentsAttachment",
            title: _t("File"),
            description: _t("Insert a file from Documents"),
            icon: "o_add_documents_icon",
            run: this.openSelectAddDocumentCreateDialog.bind(this),
        },
        powerbox_items: {
            categoryId: "media",
            commandId: "addDocumentsAttachment",
            keywords: [_t("file"), _t("document")],
        },
    };

    openSelectAddDocumentCreateDialog() {
        this.dependencies.dialog.addDialog(SelectAddDocumentCreateDialog, {
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
                isPlugin: true,
                isNewRecord: !this.config.getRecordInfo().resId,
                addDocumentsAttachment: this.addDocumentsAttachmentFromPlugin.bind(this),
                pasteDocumentsLink: this.pasteDocumentsLinkFromPlugin.bind(this),
            },
        });
    }

    async addDocumentsAttachmentFromPlugin(resIds, closeDialog) {
        let processedAttachments;
        try {
            const recordInfo = this.config.getRecordInfo();
            const resModel = recordInfo.resModel;
            const rawResId = recordInfo.resId;
            // Process res_id to handle the attachment for plugin case
            const resId =
                resModel === "ir.ui.view" || !rawResId ? false : parseInt(rawResId) || false;
            const attachmentRecords = await this.services.orm.call(
                "documents.document",
                "add_documents_attachment",
                [resIds, resModel, resId, resModel === "ir.ui.view"]
            );
            processedAttachments = await this._processAttachments(attachmentRecords);
        } catch (error) {
            this.services.notification.add(
                _t("Failed to add document(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            closeDialog();
            return;
        }
        if (this.config.onAttachmentChange) {
            processedAttachments.forEach(this.config.onAttachmentChange);
        }
        // Render
        const fileCards = processedAttachments.map(this.renderDownloadBox.bind(this));
        // Insert
        fileCards.forEach(this.dependencies.dom.insert);
        this.dependencies.history.addStep();
        this.services.notification.add(_t("Document(s) added!"), { type: "success" });
        closeDialog();
    }
    /**
     * Helper function: mainly used to convert odoo spreadsheet into .xlsx format
     */
    async _processAttachments(attachmentRecords) {
        return attachmentRecords;
    }

    async pasteDocumentsLinkFromPlugin(resIds, closeDialog) {
        let recordData;
        try {
            recordData = await this.services.orm.read("documents.document", resIds, [
                "display_name",
                "access_url",
            ]);
        } catch (error) {
            this.services.notification.add(
                _t("Failed to paste link(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            closeDialog();
            return;
        }
        recordData.forEach(({ display_name, access_url }) => {
            this.dependencies.link.insertLink(access_url, display_name);
            this.dependencies.dom.insert(" "); // Add space after each link
        });
        this.services.notification.add(_t("Link(s) pasted!"), { type: "success" });
        closeDialog();
    }

    renderDownloadBox(attachment) {
        const url = this.services.uploadLocalFiles.getURL(attachment, {
            download: true,
            unique: true,
            accessToken: true,
        });
        const { name: filename, mimetype } = attachment;
        return renderStaticFileBox(filename, mimetype, url);
    }
}

MAIN_PLUGINS.push(AddDocumentsAttachmentPlugin);
