import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

export const DocumentsRecordMixin = (component) =>
    class extends component {
        async update(changes, options = {}) {
            if ("name" in changes && !changes.name) {
                this.model.notification.add(_t("Name cannot be empty."), {
                    type: "danger",
                });
                if (Object.keys(changes).length === 1) {
                    this._discard();
                    return;
                }
                delete changes.name;
                this._setEvalContext();
            }
            const modelMultiEdit = this.model.multiEdit;
            let movedRecordsIds = this.model.root.selection.map((rec) => rec.id);
            if (this.isDetailsPanelRecord) {
                // As previewed/focused documents are not necessarily selected,
                // force `save=true` to save any changes as the record is updated
                options.save = true;
                // Prevent multiEditing/moving the (whole) selection as it is not what we intend to modify when previewing.
                this.model.multiEdit = false;
                movedRecordsIds = [this.resId];
            }
            const originalFolderId = this.data.folder_id.id;
            const ret = await super.update(changes, options);
            if (this.data.folder_id && this.data.folder_id.id !== originalFolderId) {
                this.model.root._removeRecords(movedRecordsIds);
                // Same as moving when not in preview
                this.model.env.documentsView.bus.trigger("documents-close-preview");
            }
            this.model.multiEdit = modelMultiEdit;
            if (this.isDetailsPanelRecord && this.data.type === "folder") {
                this.model.env.searchModel._reloadSearchPanel();
            }
            return ret;
        }

        isPdf() {
            return (
                this.data.mimetype === "application/pdf" ||
                this.data.mimetype === "application/pdf;base64"
            );
        }

        isRequest() {
            return (
                !this.data.shortcut_document_id &&
                this.data.type === "binary" &&
                !this.data.attachment_id
            );
        }

        isShortcut() {
            return !!this.data.shortcut_document_id;
        }

        isURL() {
            return !this.data.shortcut_document_id && this.data.type === "url";
        }

        /**
         * Return the source Document if this is a shortcut and self if not.
         */
        get shortcutTarget() {
            if (!this.isShortcut()) {
                return this;
            }
            return (
                this.model.shortcutTargetRecords.find(
                    (rec) => rec.resId === this.data.shortcut_document_id.id
                ) || this
            );
        }

        hasStoredThumbnail() {
            return this.data.thumbnail_status === "present";
        }

        isViewable() {
            const thisRecord = this.shortcutTarget;
            return (
                thisRecord.data.type !== "folder" &&
                ([
                    "image/bmp",
                    "image/gif",
                    "image/jpeg",
                    "image/png",
                    "image/svg+xml",
                    "image/tiff",
                    "image/x-icon",
                    "image/webp",
                    "application/documents-email",
                    "application/javascript",
                    "application/json",
                    "application/xml",
                    "text/xml",
                    "text/x-python",
                    "text/markdown",
                    "text/css",
                    "text/calendar",
                    "text/javascript",
                    "text/html",
                    "text/plain",
                    "application/pdf",
                    "application/pdf;base64",
                    "audio/mpeg",
                    "video/x-matroska",
                    "video/mp4",
                    "video/webm",
                ].includes(thisRecord.data.mimetype) ||
                    (thisRecord.data.url && thisRecord.data.url.includes("youtu")))
            );
        }

        async onClickPreview(ev) {
            if (this.isRequest()) {
                ev.stopPropagation();
                // kanban view support
                ev.target.querySelector(".o_kanban_replace_document")?.click();
            } else if (this.isViewable()) {
                ev.stopPropagation();
                ev.preventDefault();
                const folder = this.model.env.searchModel
                    .getFolders()
                    .filter((folder) => folder.id === this.data.folder_id.id);
                const hasPdfSplit =
                    (!this.data.lock_uid || this.data.lock_uid.id === user.userId) &&
                    folder.user_permission === "edit";
                const selection = this.model.root.selection;
                const documents = (selection.length > 1 &&
                    selection.find((rec) => rec === this) &&
                    selection.filter((rec) => rec.isViewable())) || [this];

                // Load the embeddedActions in case we open the split tool
                const embeddedActions =
                    this.data.available_embedded_actions_ids?.records.map((rec) => ({
                        id: rec.resId,
                        name: rec.data.display_name,
                    })) || [];

                await this.model.env.documentsView.bus.trigger("documents-open-preview", {
                    documents,
                    mainDocument: this,
                    isPdfSplit: false,
                    embeddedActions,
                    hasPdfSplit,
                });
            } else if (this.isURL()) {
                window.open(this.data.url, "_blank");
            }
        }

        openFolder() {
            const section = this.model.env.searchModel.getSections()[0];
            const target = this.isShortcut() ? this.shortcutTarget : this;
            const folderId = target.data.active ? target.data.id : "TRASH";
            this.model.env.searchModel.toggleCategoryValue(section.id, folderId);
            this.model.originalSelection = [this.shortcutTarget.resId];
            this.model.env.documentsView.bus.trigger("documents-expand-folder", {
                folderId: folderId,
            });
        }

        /**
         * Jump to shortcut targeted file / open targeted folder.
         */
        jumpToTarget() {
            const section = this.model.env.searchModel.getSections()[0];
            let folderId;
            if (!this.shortcutTarget.data.active) {
                folderId = "TRASH";
            } else if (this.shortcutTarget.data.type === "folder") {
                // Using doc data shortcut_document_id because isContainer record does not (need to) load shortcutTarget.
                folderId = this.data.shortcut_document_id?.id || this.shortcutTarget.data.id;
            } else {
                folderId = this.shortcutTarget.data.user_folder_id;
                if (!isNaN(folderId)) {
                    folderId = parseInt(folderId);
                }
            }
            this.model.env.searchModel.toggleCategoryValue(section.id, folderId);
            this.model.originalSelection = [this.shortcutTarget.resId];
            this.model.env.documentsView.bus.trigger("documents-expand-folder", {
                folderId: folderId,
            });
        }
    };
