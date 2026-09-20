import { getCommonEmbeddedActions } from "@documents/views/utils";
import { DETAIL_PANEL_REQUIRED_FIELDS } from "@documents/views/hooks";
import { makeActiveField } from "@web/model/relational_model/utils";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { omit } from "@web/core/utils/objects";
import { useSubEnv } from "@odoo/owl";

export const DocumentsControllerMixin = (component) =>
    class extends component {
        setup() {
            super.setup(...arguments);
            this.searchBarToggler = useSearchBarToggler();
            useSubEnv({
                searchBarToggler: this.searchBarToggler,
            });

            this.documentService = useService("document.document");
            this.firstLoadSelectId = this.documentService.initData?.documentId;
        }

        /**
         * Open document preview when the view is loaded for a specific document such as in:
         *  * Direct access to the app via a document URL / _get_access_action
         *  * In-app redirection from shortcut
         */
        openInitialPreview() {
            if (!this.firstLoadSelectId) {
                return;
            }
            const initData = this.documentService.initData;
            const doc = this.model.root.records.find(
                (record) => record.data.id === this.firstLoadSelectId
            );
            if (doc) {
                this.firstLoadSelectId = false;
                doc.selected = true;
                if (initData.openPreview) {
                    initData.openPreview = false;
                    doc.onClickPreview(new Event("click"));
                }
            }
        }

        get modelParams() {
            const modelParams = super.modelParams;
            modelParams.multiEdit = true;

            // activeFields for DocumentsDetailsPanel
            const activeFields = Object.keys(modelParams.config.activeFields);

            DETAIL_PANEL_REQUIRED_FIELDS.forEach((field) => {
                if (!activeFields.includes(field)) {
                    modelParams.config.activeFields[field] = makeActiveField();
                }
            });

            if (!activeFields.includes("res_id")) {
                modelParams.config.activeFields.res_id = makeActiveField();
                modelParams.config.activeFields.res_id.related = {
                    fields: {
                        display_name: {
                            name: "display_name",
                            type: "char",
                        },
                    },
                    activeFields: {
                        display_name: makeActiveField(),
                    },
                };
            }

            if (!activeFields.includes("tag_ids")) {
                modelParams.config.activeFields.tag_ids = makeActiveField();
                modelParams.config.activeFields.tag_ids.related = {
                    activeFields: {
                        display_name: makeActiveField({ readonly: true }),
                        color: makeActiveField(),
                    },
                    fields: {
                        display_name: {
                            name: "display_name",
                            type: "char",
                            readonly: true,
                        },
                        color: {
                            name: "color",
                            type: "integer",
                            readonly: false,
                        },
                    },
                };
            }

            if (!activeFields.includes("alias_tag_ids")) {
                modelParams.config.activeFields.alias_tag_ids = {
                    ...modelParams.config.activeFields.tag_ids,
                };
            }

            return modelParams;
        }

        /**
         * Return the common list of actions for the selected / previewed document folders.
         */
        getEmbeddedActions() {
            const embeddedActions = getCommonEmbeddedActions(this.model.targetRecords);
            return Object.fromEntries(
                embeddedActions.map((e) => [
                    e.id,
                    {
                        description: e.name,
                        callback: () => this.model.onDoAction(e.id),
                        groupNumber: 0,
                    },
                ])
            );
        }

        getTopBarActionMenuItems() {
            const embeddedActions = this.getEmbeddedActions();
            const userIsInternal = this.documentService.userIsInternal;
            return {
                ...embeddedActions,
                download: {
                    isAvailable: () => this.targetRecords.some((r) => !r.isRequest()),
                    sequence: 50,
                    description: _t("Download"),
                    icon: "fa fa-download",
                    callback: () => this.model.onDownload(),
                    groupNumber: 1,
                },
                share: {
                    isAvailable: () => userIsInternal && this.targetRecords.length > 0,
                    sequence: 51,
                    description: _t("Share"),
                    icon: "fa fa-share",
                    callback: () => this.model.onShare(),
                    groupNumber: 1,
                },
            };
        }

        getStaticActionMenuItems() {
            const selectionCount = this.targetRecords.length;
            const userIsInternal = this.documentService.userIsInternal;
            const singleSelection = selectionCount === 1 && this.targetRecords[0];
            const isInTrash = this.env.searchModel.getSelectedFolderId() === "TRASH";
            const editMode = this.targetRecords.every((r) => r.data.user_permission === "edit");
            const someActive = this.targetRecords.some((r) => r.data.active);
            const someArchived = this.targetRecords.some((r) => !r.data.active);
            const someUnlocked = this.targetRecords.some((r) => !r.data.lock_uid);
            const menuItems = super.getStaticActionMenuItems();
            const topBarActions = this.env.isSmall ? this.getTopBarActionMenuItems() : {};
            return {
                ...omit(menuItems, "archive", "delete", "duplicate", "unarchive"),
                ...topBarActions,
                duplicate: {
                    isAvailable: () => this.model.canDuplicateRecords,
                    sequence: 50,
                    description: _t("Duplicate"),
                    icon: "fa fa-copy",
                    callback: () => this.model.onDuplicate(),
                    groupNumber: 1,
                },
                trash: {
                    isAvailable: () => userIsInternal && editMode && someActive && someUnlocked,
                    sequence: 55,
                    description: _t("Move to Trash"),
                    icon: "fa fa-trash",
                    callback: () => this.model.onArchive(),
                    groupNumber: 1,
                },
                restore: {
                    isAvailable: () => someArchived,
                    sequence: 60,
                    description: _t("Restore"),
                    icon: "fa fa-history",
                    callback: () => this.model.onRestore(),
                    groupNumber: 1,
                },
                delete: {
                    isAvailable: () => this.model.canDeleteRecords,
                    sequence: 65,
                    description: _t("Delete"),
                    icon: "fa fa-trash",
                    callback: () => this.model.onDelete(),
                    groupNumber: 1,
                },
                rename: {
                    isAvailable: () => editMode && singleSelection && someUnlocked && !isInTrash,
                    sequence: 70,
                    description: _t("Rename"),
                    icon: "fa fa-edit",
                    callback: () => this.model.onRename(),
                    groupNumber: 2,
                },
                details: {
                    isAvailable: () =>
                        userIsInternal && !this.env.searchModel.context.documents_view_secondary,
                    sequence: 75,
                    description: _t("Info & tags"),
                    icon: "fa fa-info-circle",
                    callback: () => this.model.onToggleRightPanel(),
                    groupNumber: 2,
                },
                move: {
                    isAvailable: () => this.model.canMoveRecords,
                    sequence: 78,
                    description: _t("Move"),
                    icon: "fa fa-sign-in",
                    callback: () => this.model.onMove(),
                    groupNumber: 2,
                },
                shortcut: {
                    isAvailable: () => userIsInternal && !isInTrash,
                    sequence: 80,
                    description: _t("Create Shortcut"),
                    icon: "fa fa-external-link-square",
                    callback: () => this.model.onCreateShortcut(),
                    groupNumber: 2,
                },
                version: {
                    isAvailable: () => this.model.canManageVersions,
                    sequence: 85,
                    description: _t("Manage Versions"),
                    icon: "fa fa-history",
                    callback: () => this.model.onManageVersions(),
                    groupNumber: 2,
                },
                lock: {
                    isAvailable: () =>
                        userIsInternal &&
                        singleSelection &&
                        singleSelection.data.type !== "folder" &&
                        !isInTrash &&
                        editMode,
                    sequence: 90,
                    description: singleSelection?.data?.lock_uid ? _t("Unlock") : _t("Lock"),
                    icon: "fa fa-lock",
                    callback: () => this.model.onToggleLock(),
                    groupNumber: 2,
                },
                copy: {
                    isAvailable: () => selectionCount && !isInTrash,
                    sequence: 95,
                    description: _t("Copy Links"),
                    icon: "fa fa-link",
                    callback: () => this.model.onCopyLinks(),
                    groupNumber: 2,
                },
                pdf: {
                    isAvailable: () =>
                        userIsInternal &&
                        selectionCount &&
                        editMode &&
                        this.targetRecords.every(
                            (record) => record.isPdf() && !record.data.lock_uid
                        ) &&
                        !isInTrash,
                    sequence: 100,
                    description: singleSelection ? _t("Split PDF") : _t("Merge PDFs"),
                    icon: "fa fa-scissors",
                    callback: () => this.model.onSplitPDF(),
                    groupNumber: 2,
                },
            };
        }

        get showActions() {
            const previewing = !!this.rightPanelState.previewedDocument;
            const focusing = !!this.rightPanelState.focusedRecord;
            const focusedSelected =
                focusing &&
                !!this.targetRecords.find((r) => r.id === this.rightPanelState.focusedRecord.id);
            return !previewing && (!focusing || focusedSelected);
        }
    };
