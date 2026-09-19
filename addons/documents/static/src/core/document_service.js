import { AccessRightsUpdateConfirmationDialog } from "@documents/owl/components/access_update_confirmation_dialog/access_update_confirmation_dialog";
import { Document } from "./document_model";
import { DocumentsManageVersions } from "@documents/components/documents_manage_versions_panel/documents_manage_versions_panel";
import { EventBus, markup, reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { download } from "@web/core/network/download";
import { parseSearchQuery, router } from "@web/core/browser/router";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { debounce } from "@web/core/utils/timing";
import { session } from "@web/session";
import { formatFloat } from "@web/views/fields/formatters";
import { memoize } from "@web/core/utils/functions";

const { DateTime } = luxon;

// Small hack, memoize uses the first argument as cache key, but we need the orm which will not be the same.
const loadMaxUploadSize = memoize((_null, orm) =>
    orm.call("documents.document", "get_document_max_upload_limit")
);
const getDeletionDelay = memoize((_null, orm) =>
    orm.call("documents.document", "get_deletion_delay", [[]])
);

export class DocumentService {
    documentList;

    constructor(env, services) {
        this.env = env;
        /** @type {import("@mail/core/common/store_service").Store} */
        this.store = services["mail.store"];
        this.orm = services["orm"];
        this.action = services["action"];
        this.notification = services["notification"];
        this.dialog = services["dialog"];
        this.fileUpload = services["file_upload"];
        this.busService = services["bus_service"];
        this.logAccess = debounce(this._logAccess, 1000, false);
        this.currentFolderAccessToken = null;
        this.bus = new EventBus();
        this.userIsDocumentManager = false;
        this.userIsDocumentUser = false;
        this.userIsErpManager = false;
        this.userIsInternal = false;
        this.multiCompany = false;
        this.hasFolderEditorAccess = false;
        // Init data
        const urlSearch = parseSearchQuery(browser.location.search);
        const { documents_init } = session;
        const openPreview =
            Boolean(urlSearch.documents_init_open_preview) || documents_init?.open_preview;
        const documentId =
            Number(urlSearch.documents_init_document_id) || documents_init?.document_id;
        this.documentIdToRestoreOnce = documentId;
        const userFolderId = urlSearch.documents_init_user_folder_id;
        this._initData = { documentId, userFolderId, openPreview };
        if (userFolderId) {
            browser.localStorage.setItem("searchpanel_documents_document", userFolderId);
        }
        this.getSelectionActions = null;
    }

    /**
     * @returns Document id to restore if there is one otherwise undefined.
     * Note: To ensure the document is restored only once, it returns always undefined after the first call.
     */
    getOnceDocumentIdToRestore() {
        const res = this.documentIdToRestoreOnce;
        this.documentIdToRestoreOnce = undefined;
        return res;
    }

    async start() {
        [
            this.userIsDocumentManager,
            this.userIsDocumentUser,
            this.userIsErpManager,
            this.userIsInternal,
            this.multiCompany,
        ] = await Promise.all([
            user.hasGroup("documents.group_documents_manager"),
            user.hasGroup("documents.group_documents_user"),
            user.hasGroup("base.group_erp_manager"),
            user.hasGroup("base.group_user"),
            user.hasGroup("base.group_multi_company"),
        ]);
        this.hasFolderEditorAccess =
            this.userIsInternal ||
            (await this.orm.call("documents.operation", "get_any_editor_destination")).length > 0;
        const initialState =
            this.userIsInternal && JSON.parse(localStorage.getItem("documentsChatterVisible"));
        this.rightPanelReactive = reactive(
            {
                visible: initialState,
                focusedRecord: null,
                previewedDocument: null,
            },
            () => {
                localStorage.setItem("documentsChatterVisible", this.rightPanelReactive.visible);
            }
        );
    }

    /**
     * @param {Object} data
     * @returns {Document}
     */
    insert(data) {
        let document = this.store.Document.records[data.id];
        // Comparing the datapoint id here.
        if (document?.record.id !== data.record.id) {
            document = new Document();
            if ("id" in data) {
                document.id = data.id;
            }
            if ("attachment" in data) {
                document.attachment = this.store["ir.attachment"].insert(data.attachment);
            }
            if ("name" in data) {
                document.name = data.name;
            }
            if ("mimetype" in data) {
                document.mimetype = data.mimetype;
            }
            if ("url" in data) {
                document.url = data.url;
            }
            if ("displayName" in data) {
                document.displayName = data.displayName;
            }
            if ("record" in data) {
                document.record = data.record;
            }
            document.store = this.store;
            this.store.Document.records[data.id] = document;
            // Get reactive version.
            document = this.store.Document.records[data.id];
        } else {
            // Document was renamed
            if ("attachment" in data && data.name !== document.name) {
                document.attachment = this.store.Attachment.insert(data.attachment);
            }
        }
        // return reactive version
        return document;
    }

    canUploadInFolder(folder) {
        const userPermission = folder.target_user_permission || folder.user_permission;
        return (
            folder &&
            ((typeof folder.id === "number" && userPermission === "edit") ||
                (this.userIsInternal && ["MY", "RECENT", false].includes(folder.id)) ||
                (this.userIsDocumentManager && folder.id === "COMPANY"))
        );
    }

    canDownload(document) {
        return document && typeof document.id === "number";
    }

    async downloadDocuments(documents, resIds) {
        if (!resIds) {
            documents = documents.filter((rec) => !rec.isRequest());
            if (!documents.length) {
                return;
            }

            const linkDocuments = documents.filter((el) => el.data.type === "url");
            const noLinkDocuments = documents.filter((el) => el.data.type !== "url");
            // Manage link documents
            if (documents.length === 1 && linkDocuments.length) {
                // Redirect to the link
                let url = linkDocuments[0].data.url;
                url = /^(https?|ftp):\/\//.test(url) ? url : `http://${url}`;
                window.open(url, "_blank");
                return;
            } else if (noLinkDocuments.length) {
                // Download all documents which are not links
                if (noLinkDocuments.length === 1) {
                    await download({
                        data: {},
                        url: `/documents/content/${noLinkDocuments[0].data.access_token}`,
                    });
                    return;
                } else {
                    resIds = noLinkDocuments.map((rec) => rec.data.id);
                }
            } else {
                return;
            }
        }
        await download({
            data: {
                file_ids: resIds,
                zip_name: `documents-${serializeDate(DateTime.now())}.zip`,
            },
            url: "/documents/zip",
        });
    }

    isEditable(document) {
        return (
            document &&
            typeof document.id === "number" &&
            document.user_permission === "edit" &&
            (document.user_folder_id !== "COMPANY" || this.userIsDocumentManager)
        );
    }

    isFolderSharable(folder) {
        return folder && typeof folder.id === "number";
    }

    async openDialogRename(documentId) {
        return new Promise((resolve) => {
            this.action.doAction(
                {
                    name: _t("Rename"),
                    type: "ir.actions.act_window",
                    res_model: "documents.document",
                    res_id: documentId,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        active_id: documentId,
                        dialog_size: "medium",
                        form_view_ref: "documents.document_view_form_rename",
                    },
                },
                {
                    onClose: async () => {
                        resolve();
                    },
                }
            );
        });
    }

    async openDialogManageVersions(documentId) {
        this.dialog.add(DocumentsManageVersions, { documentId });
    }

    async openSharingDialog(documentIds) {
        const action = await this.orm.call("documents.sharing", "action_open", [documentIds]);
        await this.action.doAction(action, { onClose: () => this.reload() });
    }

    async openOperationDialog({
        documents,
        attachmentId,
        operation = "move",
        onClose = () => {},
        context = {},
    }) {
        documents = documents || [];
        const doc0 = documents[0];
        let name;
        const single_values = { documentName: doc0?.name };
        const multiple_values = { numberOfDocuments: documents.length.toString() };
        if (operation === "move") {
            name =
                documents.length === 1
                    ? _t("Move: %(documentName)s", single_values)
                    : _t("Move: %(numberOfDocuments)s items", multiple_values);
        } else if (operation === "shortcut") {
            name =
                documents.length === 1
                    ? _t("Create shortcut to: %(documentName)s", single_values)
                    : _t("Create shortcuts for: %(numberOfDocuments)s items", multiple_values);
        } else if (operation === "copy") {
            name =
                documents.length === 1
                    ? _t("Duplicate: %(documentName)s", single_values)
                    : _t("Duplicate: %(numberOfDocuments)s items", multiple_values);
        } else if (operation === "add") {
            name = _t("Add to documents");
        } else {
            name = operation;
        }
        this.action.doAction(
            {
                name,
                type: "ir.actions.act_window",
                res_model: "documents.operation",
                views: [[false, "form"]],
                target: "new",
            },
            {
                additionalContext: {
                    default_document_ids: documents.map((d) => d.id),
                    default_attachment_id: attachmentId || false,
                    default_operation: operation,
                    ...context,
                },
                onClose,
            }
        );
    }

    async moveToTrash(documentIds) {
        const deletionDelay = await getDeletionDelay(null, this.orm);
        const confirmed = await new Promise((resolve) => {
            const dialogProps = {
                title: _t("Move to trash"),
                body: _t(
                    "Items moved to the trash will be deleted forever after %(deletion_delay)s days.",
                    { deletion_delay: deletionDelay }
                ),
                confirmLabel: _t("Move to trash"),
                cancelLabel: _t("Discard"),
                confirm: async () => resolve(true),
                cancel: () => resolve(false),
            };
            this.dialog.add(ConfirmationDialog, dialogProps);
        });
        if (!confirmed) {
            return false;
        }
        await this.orm.call("documents.document", "action_archive", [documentIds]);
        return true;
    }

    async goToServerActionsView() {
        const userHasAccessRight = await user.checkAccessRight("ir.actions.server", "create");
        if (!userHasAccessRight) {
            return this.notification.add(
                _t("Contact your Administrator to get access if needed."),
                {
                    title: _t("Access to Server Actions"),
                    type: "info",
                }
            );
        }

        return await this.action.doActionButton({
            name: "action_open_documents_server_action_view",
            type: "object",
            resModel: "ir.actions.server",
        });
    }

    async moveOrCreateShortcut(records, targetFolder, forceShortcut, expectedAccessRightsChanges) {
        let message = "";
        const userFolderId = targetFolder.id.toString();
        if (forceShortcut) {
            await this.orm.call("documents.document", "action_create_shortcut", [
                records.all,
                userFolderId,
            ]);
            message =
                records.all.length === 1
                    ? _t("A shortcut has been created.")
                    : _t("%s shortcuts have been created.", records.all.length);
        } else {
            if (records.movableRecordIds.length) {
                message =
                    records.movableRecordIds.length === 1
                        ? _t("The document has been moved.")
                        : _t("%s documents have been moved.", records.movableRecordIds.length);
                if (expectedAccessRightsChanges) {
                    const confirmed = await new Promise((resolve) => {
                        this.dialog.add(AccessRightsUpdateConfirmationDialog, {
                            destinationFolder: targetFolder,
                            confirm: async () => resolve(true),
                            cancel: () => resolve(false),
                        });
                    });
                    if (!confirmed) {
                        return;
                    }
                }
                await this.orm.write("documents.document", records.movableRecordIds, {
                    user_folder_id: userFolderId,
                });
            }
            if (records.nonMovableRecordIds.length) {
                this.notification.add(
                    _t("At least one document could not be moved due to access rights."),
                    { type: "warning" }
                );
            }
        }
        if (message) {
            this.notification.add(message, { type: "success" });
        }
    }

    async moveToCompanyRoot(records) {
        if (!records.movableRecordIds.length) {
            return this.notification.add(
                _t("You can't move this/those folder(s) to the Company root."),
                { type: "warning" }
            );
        }
        await this.orm.write("documents.document", records.movableRecordIds, {
            user_folder_id: "COMPANY",
        });
        let message =
            records.movableRecordIds.length === 1
                ? _t("The document/folder has been moved to the Company root.")
                : _t(
                      "%s documents/folders have been moved to the Company root.",
                      records.movableRecordIds.length
                  );
        if (records.nonMovableRecordIds.length) {
            message = markup`${message}<br/>{_t("At least one document hasn't been moved.")}`;
        }
        this.notification.add(message, {
            type: records.nonMovableRecordIds.length ? "warning" : "success",
        });
    }

    async toggleFavorite(document) {
        await this.orm.write("documents.document", [document.id], {
            is_favorited: !document.is_favorited,
        });
    }

    get initData() {
        return this._initData;
    }

    reload() {
        this.bus.trigger("DOCUMENT_RELOAD");
    }

    /**
     * Update the URL with the current folder/inspected document (as an access_token).
     *
     * Thanks to the provided arguments, this method adds the access_token of the currently
     * viewed document in the URL to allow the user to share the document (or the folder)
     * by simply sharing its URL.
     * When multiple document are viewed, it removes the access_token from the URL as sharing
     * multiple document with one URL is not supported.
     * Similarly, when a document is focused but not selected, nor being previewed, the access
     * token is not put in the URL either to avoid confusion about what record it is.
     * Note that when the folderChange argument is null, the service use the preceding
     * given value if needed.
     *
     * @param {object} folderChange the new folder or null if not changed
     * @param {object[]} inspectedDocuments the currently inspected documents (can be undefined)
     * @param {boolean} forceInspected force updating to single inspected document token, or ignored
     */
    updateDocumentURL(folderChange, inspectedDocuments, forceInspected) {
        let accessToken = undefined;
        if (folderChange) {
            accessToken = folderChange.access_token;
            this.currentFolderAccessToken = accessToken;
        } else if (inspectedDocuments && inspectedDocuments.length === 1) {
            const record = inspectedDocuments[0];
            if (
                forceInspected ||
                record.selected ||
                record.isContainer ||
                this.rightPanelReactive.previewedDocument?.record.id === record.id
            ) {
                accessToken = record.data.access_token;
            }
        } else if (!inspectedDocuments || inspectedDocuments.length === 0) {
            accessToken = this.currentFolderAccessToken;
        }
        router.pushState({ access_token: accessToken });
    }

    /**
     * Refresh URL with the last folder (folderChange given to updateDocumentURL).
     *
     * Goal: When using an action the router loses its state.
     * This method is used to push the state already saved in this service
     * (the current folder) to the router state.
     */
    updateDocumentURLRefresh() {
        const tokenToShow = this.focusedRecord?.data.access_token || this.currentFolderAccessToken;
        if (tokenToShow) {
            router.pushState({ access_token: tokenToShow });
        }
    }

    _logAccess(accessToken) {
        if (!accessToken) {
            return;
        }
        rpc(`/documents/touch/${encodeURIComponent(accessToken)}`);
    }

    /**
     * Return all the actions, and the embedded action for the given folders.
     *
     * EG: [{id: 1337, name: "Create Activity", is_embedded: true}, ...]
     */
    async getActions(folderId) {
        if (!this.userIsInternal) {
            return [];
        }
        return await this.orm.call("documents.document", "get_documents_actions", [folderId]);
    }

    /**
     * Enable the action for the given folder.
     */
    async enableAction(folderId, actionId) {
        return await this.orm.call("documents.document", "action_folder_embed_action", [
            folderId,
            actionId,
        ]);
    }

    get focusedRecord() {
        return this.rightPanelReactive.focusedRecord;
    }

    /**
     * Support reactivity for focused record and update URL.
     * @param record
     * @param forceSelected to force updating the URL to record's token,
     *   necessary because the service can't easily know if a record is selected.
     */
    focusRecord(record, forceSelected) {
        if (this.focusedRecord !== record) {
            this.rightPanelReactive.focusedRecord = record;
            this.updateDocumentURL(null, record ? [record] : null, forceSelected);
            if (record) {
                this.logAccess(record.data.access_token);
            }
        }
    }

    toggleRightPanelVisibility() {
        this.rightPanelReactive.visible = !this.rightPanelReactive.visible;

        if (this.rightPanelReactive.visible) {
            this.observer = new MutationObserver(() => {
                const chatterContainer = document.querySelector(".o-mail-Thread");
                if (chatterContainer && this.env.isSmall) {
                    chatterContainer.scrollIntoView({ behavior: "smooth" });
                    this.observer.disconnect();
                    return;
                }
                const view = this.action.currentController?.props.type;
                if (chatterContainer && ["kanban", "list"].includes(view)) {
                    const selectedRecordClass =
                        view === "kanban"
                            ? ".o_kanban_record.o_record_selected"
                            : ".o_data_row.o_data_row_selected";
                    const selectedRecords = document.querySelectorAll(selectedRecordClass);
                    if (selectedRecords?.length > 0) {
                        selectedRecords[0].scrollIntoView({
                            behavior: "instant",
                            block: view === "kanban" ? "start" : "center",
                        });
                    }
                    this.observer.disconnect();
                }
            });
            if (document.querySelector(".o_documents_content")) {
                this.observer.observe(document.querySelector(".o_documents_content"), {
                    childList: true,
                    subtree: true,
                });
            }
        }
    }

    /**
     * Set the previewed document and send an event to notify the change.
     */
    setPreviewedDocument(document) {
        this.rightPanelReactive.previewedDocument = document;
        if (document) {
            this.focusRecord(document.record);
        }
    }

    async uploadDocument(files, accessToken, context) {
        const fileArray = [...files];
        const maxUploadSize = await loadMaxUploadSize(null, this.orm);
        const validFiles = fileArray.filter((file) => file.size <= maxUploadSize);
        if (validFiles.length !== 0) {
            const encodedToken = encodeURIComponent(accessToken || "");
            await this.fileUpload.upload(`/documents/upload/${encodedToken}`, validFiles, {
                buildFormData: (formData) => {
                    if (context) {
                        for (const key of [
                            "default_user_folder_id",
                            "default_partner_id",
                            "default_res_id",
                            "default_res_model",
                        ]) {
                            if (context[key]) {
                                formData.append(key.replace("default_", ""), context[key]);
                            }
                        }
                        if (context.allowed_company_ids) {
                            formData.append(
                                "allowed_company_ids",
                                JSON.stringify(context.allowed_company_ids)
                            );
                        }
                        if (context.document_id) {
                            formData.append("document_id", context.document_id);
                        }
                    }
                },
                displayErrorNotification: false,
            });
        }
        if (validFiles.length >= fileArray.length) {
            return;
        }
        const message = _t(
            "Some files could not be uploaded (max size: %s).",
            formatFloat(maxUploadSize, { humanReadable: true })
        );
        this.notification.add(message, { type: "danger" });
    }
}

export const documentService = {
    dependencies: [
        "action",
        "bus_service",
        "dialog",
        "file_upload",
        "mail.store",
        "notification",
        "orm",
    ],
    async start(env, services) {
        const service = new DocumentService(env, services);
        await service.start();
        return service;
    },
};

registry.category("services").add("document.document", documentService);
