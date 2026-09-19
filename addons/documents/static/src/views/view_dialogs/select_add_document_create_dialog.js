import { _t } from "@web/core/l10n/translation";
import { omit } from "@web/core/utils/objects";

import { useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class SelectAddDocumentCreateDialog extends SelectCreateDialog {
    static template = "documents.SelectAddDocumentCreateDialog";
    static props = {
        ...SelectCreateDialog.props,
        chatterParams: { type: Object },
        resModel: { type: String },
        title: { type: String },
        domain: { type: Array, optional: true },
        context: { type: Object, optional: true },
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.store = useService("mail.store");
        this.notification = useService("notification");

        const { thread = {}, model, resId } = this.props.chatterParams || this.props;
        this.model = thread.model ?? model;
        this.resId = thread.id ?? resId;
    }

    get viewProps() {
        // We force list view to be used in the dialog (even for smaller screens)
        const baseProps = super.viewProps;
        return {
            ...omit(baseProps, "forceGlobalClick", "display"),
            type: "list",
            allowSelectors: true,
        };
    }

    get addDocumentsAttachmentMethod() {
        return this.props.chatterParams?.addDocumentsAttachment || this.addDocumentsAttachment;
    }

    get pasteDocumentsLinkMethod() {
        return this.props.chatterParams?.pasteDocumentsLink || this.pasteDocumentsLink;
    }

    get isPlugin() {
        return this.props.chatterParams?.isPlugin;
    }

    get isNewRecord() {
        return this.props.chatterParams?.isNewRecord;
    }

    /**
     * Pastes document/s share links.
     * @param {Array} resIds - List of resIDs of the selected records (documents).
     */
    async pasteDocumentsLink(resIds) {
        let response;
        try {
            response = await this.orm.read("documents.document", resIds, [
                "display_name",
                "access_url",
            ]);
        } catch (error) {
            this.notification.add(
                _t("Failed to paste link(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            this.props.close();
            return;
        }
        if (this.props.chatterParams.isFromFullComposer) {
            this.props.chatterParams.addDocumentsBus.trigger("PASTE_SHARE_LINKS", {
                links: response,
            });
        } else {
            this.addToThread(this.model, this.resId);
            const shareLinks = response
                .map(({ display_name, access_url }) => `${display_name}: ${access_url}`)
                .join("\n");
            this.props.chatterParams.composer.composerText += `\n${shareLinks}`;
        }
        this.notification.add(_t("Link(s) pasted!"), { type: "success" });
        this.props.close();
    }

    /**
     * Adds the document (as an attachment) to the composer.
     * @param {Array} resIds - List of resIDs of the selected records (documents).
     */
    async addDocumentsAttachment(resIds) {
        let processedAttachments;
        try {
            // Temporary linked to the composer with id 0 to be garbage collected if not re-linked to the thread
            // (similar to what is done when uploading a file)
            const attachmentRecords = await this.orm.call(
                "documents.document",
                "add_documents_attachment",
                [resIds, "mail.compose.message", 0]
            );
            processedAttachments = await this._processAttachments(attachmentRecords);
        } catch (error) {
            this.notification.add(
                _t("Failed to add document(s): ") + (error.data?.message || error.toString()),
                { type: "danger" }
            );
            this.props.close();
            return;
        }
        const thread = this.props.chatterParams?.thread || this.addToThread(this.model, this.resId);
        const composer = this.props.chatterParams?.composer || thread.composer;

        const attachmentIds = [];
        for (const { name, ...attachmentRecord } of processedAttachments) {
            const extension = name.slice(Math.max(0, name.lastIndexOf(".") + 1));
            composer.attachments.push({ name, extension, ...attachmentRecord });
            attachmentIds.push(attachmentRecord.id);
        }
        this.props.chatterParams.saveRecordHandler?.(attachmentIds);
        this.props.close();
    }

    /**
     * Helper function: mainly used to convert odoo spreadsheet into .xlsx format
     */
    async _processAttachments(attachmentRecords) {
        return attachmentRecords;
    }

    /**
     * Helper method responsible to return the new thread object.
     * @param {String} currentModel - Model of the current thread.
     * @param {Number} currentChatterRecordId - ID of the current chatter record.
     */
    addToThread(currentModel, currentChatterRecordId) {
        return this.store.Thread.insert({
            model: currentModel,
            id: currentChatterRecordId,
        });
    }
}
