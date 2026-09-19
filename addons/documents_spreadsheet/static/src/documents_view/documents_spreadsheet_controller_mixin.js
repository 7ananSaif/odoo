import { TemplateDialog } from "@documents_spreadsheet/spreadsheet_template/spreadsheet_template_dialog";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SpreadsheetCloneCSVXlsxDialog } from "@documents_spreadsheet/spreadsheet_clone_xlsx_dialog/spreadsheet_clone_xlsx_dialog";
import { _t } from "@web/core/l10n/translation";

import { XLSX_MIME_TYPES } from "@documents_spreadsheet/helpers";

export const DocumentsSpreadsheetControllerMixin = () => ({
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.documentService = useService("document.document");
        this.notification = useService("notification");
        // Hack-ish way to do this but the function is added by a hook which we can't really override.
        this.baseOnOpenDocumentsPreview = this.onOpenDocumentsPreview.bind(this);
        this.onOpenDocumentsPreview = this._onOpenDocumentsPreview.bind(this);
    },

    /**
     * Prevents spreadsheets from being in the viewable attachments list
     * when previewing a file in the FileViewer.
     *
     * @override
     */
    isRecordPreviewable(record) {
        return (
            super.isRecordPreviewable(...arguments) &&
            !["spreadsheet", "frozen_spreadsheet"].includes(record.data.handler)
        );
    },

    /**
     * @override
     */
    async _onOpenDocumentsPreview({ mainDocument }) {
        const mainDocumentOrTarget = mainDocument.shortcutTarget;
        if (["spreadsheet", "frozen_spreadsheet"].includes(mainDocumentOrTarget.data.handler)) {
            this.action.doAction({
                type: "ir.actions.client",
                tag: "action_open_spreadsheet",
                params: {
                    spreadsheet_id: mainDocumentOrTarget.resId,
                },
            });
        } else if (
            XLSX_MIME_TYPES.includes(mainDocumentOrTarget.data.mimetype) ||
            mainDocumentOrTarget.data.mimetype === "text/csv"
        ) {
            // Keep MainDocument as `active` can be different for shortcut and target.
            if (!mainDocument.data.active) {
                this.dialogService.add(ConfirmationDialog, {
                    title: _t("Restore file?"),
                    body: _t(
                        "Spreadsheet files cannot be handled from the Trash. Would you like to restore this document?"
                    ),
                    cancel: () => {},
                    confirm: async () => {
                        await this.orm.call("documents.document", "action_unarchive", [
                            mainDocument.resId,
                        ]);
                        this.env.searchModel.toggleCategoryValue(
                            1,
                            mainDocument.data.folder_id.id ?? false
                        );
                    },
                    confirmLabel: _t("Restore"),
                });
            } else if (this.documentService.userIsInternal) {
                const fileType = mainDocument.data.mimetype === "text/csv" ? "CSV" : "Excel";
                this.dialogService.add(SpreadsheetCloneCSVXlsxDialog, {
                    title: fileType + _t(" file preview"),
                    cancel: () => {},
                    cancelLabel: _t("Discard"),
                    documentId: mainDocumentOrTarget.resId,
                    confirmLabel: _t("Open with Odoo Spreadsheet"),
                });
            }
        } else {
            return this.baseOnOpenDocumentsPreview(...arguments);
        }
    },

    async onClickCreateSpreadsheet(ev) {
        const folderId = this.env.searchModel.getSelectedFolderId() || undefined;
        const context = this.props.context;
        if (folderId === "COMPANY") {
            context.default_owner_id = false;
        }
        this.dialogService.add(TemplateDialog, {
            folderId,
            context,
            folders: this.env.searchModel
                .getFolders()
                .filter((folder) => folder.id && typeof folder.id === "number"),
        });
    },

    async onClickFreezeAndShareSpreadsheet() {
        const selection = this.targetRecords;
        if (
            selection.length !== 1 ||
            !["spreadsheet", "frozen_spreadsheet"].includes(selection[0].data.handler)
        ) {
            this.notification.add(_t("Select one and only one spreadsheet"));
            return;
        }

        const doc = selection[0];

        // Freeze the spreadsheet
        await loadBundle("spreadsheet.o_spreadsheet");
        const { fetchSpreadsheetModel, freezeOdooData } = odoo.loader.modules.get(
            "@spreadsheet/helpers/model"
        );
        const model = await fetchSpreadsheetModel(this.env, "documents.document", doc.resId);
        const spreadsheetData = JSON.stringify(await freezeOdooData(model));
        const excelFiles = model.exportXLSX().files;

        // Create a new <documents.document> with the frozen data
        const record = await this.orm.call("documents.document", "action_freeze_and_copy", [
            doc.resId,
            spreadsheetData,
            excelFiles,
        ]);

        await this.env.searchModel._reloadSearchModel(true);
        await this.documentService.openSharingDialog([record.id]);
    },

    getTopBarActionMenuItems() {
        const isInTrash = this.env.searchModel.getSelectedFolderId() === "TRASH";
        const menuItems = super.getTopBarActionMenuItems();
        const selectionCount = this.model.targetRecords.length;
        const singleSelection = selectionCount === 1 && this.targetRecords[0];
        menuItems.download.isAvailable = () =>
            this.model.targetRecords.some(
                (r) => !r.isRequest() && r.data.handler !== "spreadsheet"
            );
        const prevShareAvailable = menuItems.share.isAvailable || (() => true);
        menuItems.share.isAvailable = () =>
            prevShareAvailable() &&
            !(isInTrash && this.model.targetRecords.some((r) => r.data.handler === "spreadsheet"));
        return {
            ...menuItems,
            freezeAndShare: {
                isAvailable: () =>
                    !isInTrash &&
                    this.documentService.userIsInternal &&
                    singleSelection?.data?.handler === "spreadsheet",
                sequence: 52,
                description: _t("Freeze and Share"),
                icon: "fa fa-share-alt",
                callback: () => this.onClickFreezeAndShareSpreadsheet(),
                groupNumber: 1,
            },
        };
    },

    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems(...arguments);
        menuItems.insert.isAvailable = () => this.documentService.userIsInternal;
        return menuItems;
    },
});
