import { browser } from "@web/core/browser/browser";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { getCommonEmbeddedActions } from "@documents/views/utils";

export const DocumentsModelMixin = (component) =>
    class extends component {
        setup(params) {
            super.setup(...arguments);
            if (this.config.resModel === "documents.document") {
                this.originalSelection = params.state?.sharedSelection;
            }
            this.dialogService = useService("dialog");
            this.documentService = useService("document.document");
        }

        exportSelection() {
            return this.targetRecords.map((rec) => rec.resId);
        }

        /**
         * Also load the total file size
         * @override
         */
        async load() {
            const selection = this.root?.selection;
            if (!this.originalSelection && selection && selection.length > 0) {
                this.originalSelection = selection.map((rec) => rec.resId);
            }
            for (const arg of arguments) {
                arg.context["skip_res_field_check"] = true;
            }
            const res = await super.load(...arguments);
            if (this.config.resModel !== "documents.document") {
                return res;
            }
            this.env.searchModel.skipLoadClosePreview
                ? (this.env.searchModel.skipLoadClosePreview = false)
                : this.env.documentsView.bus.trigger("documents-close-preview");
            this._reapplySelection();
            this._computeFileSize();
            this.shortcutTargetRecords = this.orm.isSample
                ? []
                : await this._loadShortcutTargetRecords();
            return res;
        }

        _reapplySelection() {
            const records = this.root.records;
            if (this.originalSelection && this.originalSelection.length > 0 && records) {
                const originalSelection = new Set(this.originalSelection);
                records.forEach((record) => {
                    record.selected = originalSelection.has(record.resId);
                });
                delete this.originalSelection;
            }
        }

        _computeFileSize() {
            let size = 0;
            if (this.root.groups) {
                size = this.root.groups.reduce(
                    (size, group) => size + group.aggregates.file_size,
                    0
                );
            } else if (this.root.records) {
                size = this.root.records.reduce((size, rec) => size + rec.data.file_size, 0);
            }
            size /= 1000 * 1000; // in MB
            this.fileSize = Math.round(size * 100) / 100;
        }

        async _loadShortcutTargetRecords() {
            const shortcuts = this.root.records.filter(
                (record) => !!record.data.shortcut_document_id
            );
            if (!shortcuts.length) {
                return [];
            }
            const shortcutTargetRecords = [];
            const targetRecords = await this._loadRecords({
                ...this.config,
                resIds: shortcuts.map((record) => record.data.shortcut_document_id.id),
            });
            for (const targetRecord of targetRecords) {
                shortcutTargetRecords.push(this._createRecordDatapoint(targetRecord));
            }
            return shortcutTargetRecords;
        }

        _createRecordDatapoint(data, mode = "readonly") {
            return new this.constructor.Record(
                this,
                {
                    context: this.config.context,
                    activeFields: this.config.activeFields,
                    resModel: this.config.resModel,
                    fields: this.config.fields,
                    resId: data.id || false,
                    resIds: data.id ? [data.id] : [],
                    isMonoRecord: true,
                    mode,
                },
                data,
                { manuallyAdded: !data.id }
            );
        }

        async _notifyChange() {
            await this.load();
            await this.notify();
            await this.env.searchModel._reloadSearchModel(true);
            // The preview will be closed, just update the state for now
            this.documentService.setPreviewedDocument(null);
        }

        get isDomainSelected() {
            return this.root.isDomainSelected && !this.documentService.previewedDocument;
        }

        getResIds(extraDomain) {
            if (extraDomain) {
                const newDomain = Domain.and([this.root.domain, extraDomain]).toList();
                return this.orm.search("documents.document", newDomain, {
                    limit: this.activeIdsLimit,
                    context: this.root.context,
                });
            }
            return this.root.getResIds(true);
        }

        get targetRecords() {
            return this.documentService.rightPanelReactive.previewedDocument
                ? [this.documentService.rightPanelReactive.previewedDocument.record]
                : this.root.selection;
        }

        get canManageVersions() {
            if (this.targetRecords.length !== 1) {
                return false;
            }
            const singleSelection = this.targetRecords[0];
            const currentFolder = this.env.searchModel.getSelectedFolder();
            return (
                this.documentService.userIsInternal &&
                singleSelection &&
                currentFolder?.id !== "TRASH" &&
                singleSelection.data.type === "binary" &&
                singleSelection.data.attachment_id &&
                !singleSelection.data.lock_uid
            );
        }

        get canDeleteRecords() {
            // Portal user can delete their own documents while internal user can only delete document in the Trash.
            const documents = this.targetRecords.map((r) => r.data);
            if (this.documentService.userIsInternal) {
                return documents.some((d) => !d.active);
            }
            return documents.every(
                (r) =>
                    r.owner_id?.id === user.userId &&
                    ["binary", "url"].includes(r.type) &&
                    typeof r.folder_id?.id === "number" &&
                    this.env.searchModel.getFolderById(r.folder_id.id).user_permission === "edit"
            );
        }

        get canDuplicateRecords() {
            return (
                this.documentService.hasFolderEditorAccess &&
                this.targetRecords.every((r) => !r.data.lock_uid && r.data.active)
            );
        }

        get canMoveRecords() {
            return (
                this.documentService.hasFolderEditorAccess &&
                this.targetRecords.some((r) => r.data.user_can_move)
            );
        }

        /**
         * Copy the links (comma-separated) of the selected documents.
         */
        async onCopyLinks() {
            const documents = this.targetRecords;
            const linksToShare =
                documents.length > 1
                    ? documents.map((d) => d.data.access_url).join(", ")
                    : documents[0].data.access_url;

            await browser.navigator.clipboard.writeText(linksToShare);
            const message =
                documents.length > 1
                    ? _t("Links copied to clipboard!")
                    : _t("Link copied to clipboard!");
            this.notification.add(message, { type: "success" });
        }

        /**
         * Lock / unlock the selected record.
         */
        async onToggleLock() {
            if (this.targetRecords.length !== 1) {
                return;
            }
            const record = this.targetRecords[0];
            if (record.data.lock_uid && record.data.lock_uid.id !== user.userId) {
                this.dialogService.add(ConfirmationDialog, {
                    title: _t("Warning"),
                    body: _t(
                        "This document is locked by %s.\nAre you sure you want to unlock it?",
                        record.data.lock_uid.display_name
                    ),
                    confirmLabel: _t("Unlock"),
                    confirm: async () => {
                        await this.orm.call("documents.document", "toggle_lock", [record.data.id]);
                        await this._notifyChange();
                    },
                    cancelLabel: _t("Discard"),
                    cancel: () => {},
                });
            } else {
                await this.orm.call("documents.document", "toggle_lock", [record.data.id]);
                await this._notifyChange();
            }
        }

        /**
         * Open/Close the chatter (the info will be stored in the local storage of the current user).
         */
        async onToggleRightPanel() {
            await this.documentService.toggleRightPanelVisibility();
        }

        /**
         * Open dialog to create shortcut(s) for the selected document(s).
         */
        async onCreateShortcut() {
            const documents = this.targetRecords;
            await this.documentService.openOperationDialog({
                documents: this.isDomainSelected
                    ? (await this.getResIds()).map((d) => ({ id: d }))
                    : documents.map((d) => ({
                          id: d.data.id,
                          name: d.data.name,
                      })),
                operation: "shortcut",
                onClose: async () => this._notifyChange(),
            });
        }

        /**
         * Unlink the selected documents if they are archived.
         */
        async onDelete() {
            const confirmed = await new Promise((resolve) => {
                const dialogProps = {
                    title: _t("Delete permanently"),
                    body:
                        this.root.isDomainSelected || this.root.selection.length > 1
                            ? _t(
                                  "Are you sure you want to permanently erase the selected documents?"
                              )
                            : _t(
                                  "Are you sure you want to permanently erase the selected document?"
                              ),
                    confirmLabel: _t("Delete permanently"),
                    cancelLabel: _t("Discard"),
                    confirm: async () => resolve(true),
                    cancel: () => resolve(false),
                };
                this.dialogService.add(ConfirmationDialog, dialogProps);
            });
            if (!confirmed) {
                return;
            }
            if (!this.isDomainSelected) {
                const records = !this.documentService.userIsInternal
                    ? this.targetRecords
                    : this.targetRecords.filter((r) => !r.data.active);
                await this.root.deleteRecords(records);
            } else {
                const resIds = !this.documentService.userIsInternal
                    ? await this.getResIds()
                    : await this.getResIds([["active", "=", false]]);
                await this.orm.unlink("documents.document", resIds, {
                    context: this.root.context,
                });
            }
            await this._notifyChange();
        }

        /**
         * Send the selected documents to the trash.
         */
        async onArchive() {
            const records = this.targetRecords.filter((r) => r.data.active && !r.data.lock_uid);
            const recordIds = this.isDomainSelected
                ? await this.getResIds([["lock_uid", "=", false]])
                : records.map((rec) => rec.data.id);
            await this.documentService.moveToTrash(recordIds);
            await this._notifyChange();
        }

        /**
         * Duplicate the selected documents.
         */
        async onDuplicate() {
            const documents = this.targetRecords;
            await this.documentService.openOperationDialog({
                documents: this.isDomainSelected
                    ? (await this.getResIds()).map((d) => ({ id: d }))
                    : documents.map((d) => ({
                          id: d.data.id,
                          name: d.data.name,
                      })),
                operation: "copy",
                onClose: async () => this.env.searchModel._reloadSearchModel(true),
            });
        }

        /**
         * Open the "Version" modal.
         */
        async onManageVersions() {
            await this.documentService.openDialogManageVersions(this.targetRecords[0].data.id);
        }

        /**
         * Restore the selected documents.
         */
        async onRestore() {
            const records = this.targetRecords.filter((r) => !r.data.active);
            const recordIds = this.isDomainSelected
                ? await this.getResIds([["active", "=", false]])
                : records.map((r) => r.data.id);
            await this.orm.call("documents.document", "action_unarchive", [recordIds]);
            await this.env.searchModel._reloadSearchModel(true);
        }

        /**
         * Open the split / merge tool on the selected PDFs.
         */
        onSplitPDF() {
            const documents = this.targetRecords;
            if (!documents?.length || !documents.every((d) => d.isPdf())) {
                return;
            }

            this.env.documentsView.bus.trigger("documents-open-preview", {
                documents: documents,
                mainDocument: this.targetRecords[0],
                isPdfSplit: true,
                hasPdfSplit: true,
                embeddedActions: getCommonEmbeddedActions(documents),
            });
        }

        /**
         * Open the "rename" form view on the selected record.
         */
        async onRename() {
            if (this.targetRecords.length !== 1) {
                return;
            }
            await this.documentService.openDialogRename(this.targetRecords[0].data.id);
            await this._notifyChange();
        }

        /**
         * Open the permission panel of the selected document.
         */
        async onShare() {
            const documents = this.targetRecords;
            await this.documentService.openSharingDialog(documents.map((d) => d.data.id));
        }

        /**
         * Open dialog to move the selected document(s).
         */
        async onMove() {
            const documents = this.targetRecords.filter((r) => r.data.user_can_move);
            await this.documentService.openOperationDialog({
                documents: this.isDomainSelected
                    ? (await this.getResIds()).map((d) => ({ id: d }))
                    : documents.map((d) => ({
                          id: d.data.id,
                          name: d.data.name,
                      })),
                operation: "move",
                onClose: async () => this.env.searchModel._reloadSearchModel(true),
            });
        }

        /**
         * Execute the given `ir.embedded.action` on the current selected documents.
         */
        async onDoAction(actionId) {
            const documentIds = this.targetRecords.map((record) => record.data.id);

            const context = {
                active_model: "documents.document",
                active_ids: documentIds,
            };
            const action = await this.orm.call(
                "documents.document",
                "action_execute_embedded_action",
                [actionId],
                { context }
            );
            if (action) {
                // We might need to do a client action (e.g. to open the "Link Record" wizard)
                await this.action.doAction(action, {
                    onClose: () => {
                        this._notifyChange();
                    },
                });
                if (action.tag !== "display_notification") {
                    return;
                }
            }
            await this._notifyChange();
        }

        /**
         * Download the selected documents.
         */
        async onDownload() {
            if (this.isDomainSelected) {
                const domain = Domain.and([
                    [["type", "!=", "url"]],
                    Domain.or([
                        [["type", "=", "folder"]],
                        [["attachment_id", "!=", false]],
                        [["shortcut_document_id.attachment_id", "!=", false]],
                    ]),
                ]);
                const resIds = await this.getResIds(domain);
                this.documentService.downloadDocuments(this.targetRecords, resIds);
            } else {
                this.documentService.downloadDocuments(this.targetRecords);
            }
        }
    };
