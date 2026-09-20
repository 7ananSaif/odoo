import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SignTemplateControlPanel } from "./sign_template_control_panel";
import { SignTemplateBody } from "./sign_template_body";
import { Component, onWillStart, useState } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { SignTemplateSidebar } from "./sign_template_sidebar";
import { rpc } from "@web/core/network/rpc";
import { useSetupAction } from "@web/search/action_hook";

export class SignTemplate extends Component {
    static template = "sign.Template";
    static components = {
        SignTemplateControlPanel,
        SignTemplateBody,
        SignTemplateSidebar,
    };
    static props = {
        ...standardActionServiceProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        const params = this.props.action.params;
        this.templateID = params.id;
        const name = this.props.action.name || params.name;

        if (this.templateID) {
            this.props.updateActionState({ id: this.templateID });
        }
        if (name) {
            this.env.config.setDisplayName(name);
            this.props.updateActionState({ name: name });
        }
        this.actionType = params.sign_edit_call || "";
        this.resModel = params.resModel || "";
        this.referenceDoc = this.props.action.context.default_reference_doc;
        this.activityId = this.props.action.context.default_activity_id;
        this.signStatus = useState({
            isTemplateChanged: false,
            // isSignTemplateSaved is used as a flag to know if the template is saved or not.
            // It is used to show a notification when the user tries to edit the uploaded document.
            // It is set to true when the template is saved from the backend.
            isSignTemplateSaved: this.resModel === "sign.request" ? true : false,
            save : () => {},
            discardChanges : () => {},
            isDiscardingChanges: false,
        });

        onWillStart(async () => {
            if (!this.templateID) {
                return this.goBackToKanban();
            }
            return Promise.all([this.checkManageTemplateAccess(), this.fetchTemplateData(), this.fetchFont()]);
        });
        this.state = useState({
            signers: [],
            nextId: 0,
            documentIds: [],
            selectedDocumentId: 0,
            iframe: undefined,
        });
        this.waitForIframeToLoad();

        useSetupAction({
            beforeLeave: async () => {
                if (this.signStatus.isTemplateChanged && !this.signStatus.isSignTemplateSaved && this.signTemplate.active) {
                    await this.signStatus.save();
                    this.notification.add(_t("Saved"), { type: "success" });
                }
                // When the user clicks on "discard" from the status indicator, do not show the confirmation dialog.
                else if (!this.signTemplate.active && !this.signStatus.isDiscardingChanges) {
                    /* When user is directly sending a document for signing by clicking
                    on the 'Send' or 'Sign Now' button from wizard, we don't want to show the confirmation dialog. */
                    const isSignRequest = await this.orm.searchCount(
                        "sign.request",
                        [['template_id', '=', this.signTemplate.id]],
                        { limit: 1 }
                    );
                    return isSignRequest || this.showConfirmationDialog();
                }
                this.isDiscardingChanges = false;
            }
        });
    }

    get showSidebar() {
        return !this.env.isSmall;
    }

    /**
     * Checks if there are signers without sign items in the template
     * @returns {Boolean}
     */
    get hasSignersWithoutItems() {
        return this.state.signers.some(signer => signer.itemsCount === 0);
    }

    get signTemplateSidebarProps() {
        this.signItemTypesActive = this.signItemTypes.filter(item => item.active);
        return {
            signItemTypes: this.signItemTypesActive,
            isSignRequest: this.resModel === "sign.request",
            updateRoleName: (roleId, roleName) => this.updateRoleName(roleId, roleName),
            deleteRole: (roleId) => this.deleteRole(roleId),
            signTemplateId: this.signTemplate.id,
            signers: this.state.signers,
            hasSignRequests: this.hasSignRequests,
            documents: this.state.documents,
            selectedDocumentId: this.state.selectedDocumentId,
            /* Update callbacks binding for parent. */
            onEditTemplate: () => this.onEditTemplate(),
            updateCollapse: (id, value) => this.updateCollapse(id, value),
            updateSigners: this.updateSigners.bind(this),
            pushNewSigner: this.pushNewSigner.bind(this),
            updateDocumentName: (documentId, newName) => this.updateDocumentName(documentId, newName),
            updateSelectedDocument: (id) => this.updateSelectedDocument(id),
            updateDocuments: () => this.updateDocuments(),
            deleteDocument: (documentId) => this.deleteDocument(documentId),
            moveDocumentUp: (documentId) => this.moveDocument(documentId, -1),
            moveDocumentDown: (documentId) => this.moveDocument(documentId, 1),
            onUpdateDocument: this.onUpdateDocument.bind(this),
            saveManually: () => this.signStatus.save(),
        }
    }

    async onEditTemplate() {
        const duplicatedTemplateIds = await this.orm.call("sign.template", "copy", [
            [this.signTemplate.id],
        ]);

        this.action.doAction({
            type: "ir.actions.client",
            tag: "sign.Template",
            name: _t("Edit Template"),
            params: {
                id: duplicatedTemplateIds[0],
            },
        });
    }

    updateRoleName(roleId, roleName) {
        this.orm.write("sign.item.role", [roleId], { name: roleName });
        const signer = this.state.signers.find((s) => s.roleId === roleId);
        if (signer) {
            signer.name = roleName;
        }
        this.state.documents.forEach(document => document.iframe?.updateRoleName(roleId, roleName));
    }

    deleteRole(roleId) {
        this.state.documents.forEach(document => document.iframe.deleteRole(roleId));
    }

    waitForIframeToLoad() {
        //TODO: this save methods does n rpc requests, where n is the number of documents.
        //To bo optimized later.
        this.signStatus.save = async () => {
            const saveDocuments = this.state.documents.filter(document => !document.deleted).map(document => document.iframe?.saveChangesOnBackend());
            // Wait for all save operations to complete
            return Promise.all(saveDocuments);
        };
        let iframesLoaded = false;
        if (this.state.documents) {
            iframesLoaded = true;
            this.state.documents.forEach((document) => {
                if (!document.iframe) {
                    iframesLoaded = false;
                }
            });
        }
        if (iframesLoaded) {
            this.orm.call("sign.template", "get_template_items_roles_info", [this.templateID]).then(info => {
                /* Make all signers collapsed when loading for the first time. */
                const updatedInfo = info.map(item => ({
                    ...item,
                    isCollapsed: true,
                    isInputFocused: false,
                    itemsCount: 0,
                }));

                /* Make the last signer uncollapsed. */
                if (updatedInfo.length > 0)
                    updatedInfo[updatedInfo.length - 1].isCollapsed = false;

                /* Update signer's loaded information. */
                this.updateSigners(updatedInfo);
                this.state.nextId = this.state.signers.length;

                /* We must have at least one signer after load. */
                if (updatedInfo.length == 0)
                    this.pushNewSigner();

                /* Set callback for tracking number of items of each signer and load font. */
                this.state.documents.forEach(document => {
                    document.iframe.setFont(this.font);
                });
            });
        } else {
            setTimeout(() => this.waitForIframeToLoad(), 50);
        }
    }

    updateSigners(newSigners) {
        this.state.signers = newSigners;
        this.state.signers.forEach(signer => {
            this.state.documents.forEach(document => {
                document.iframe.setRoleColor(signer.roleId, signer.colorId);
            });
        });
    }

    updateSignItemsCount() {
        const updatedSigners = this.state.signers;
        updatedSigners.forEach(signer => {
            signer.itemsCount = 0;
            this.state.documents.forEach((document) => {
                if (document.iframe.signItemsCountByRole) {
                    signer.itemsCount += document.iframe.signItemsCountByRole[signer.roleId] || 0;
                }
            })
        });
        this.updateSigners(updatedSigners);
    }

    async pushNewSigner() {
        const name = _t("Signer %s", this.state.signers.length + 1);
        const roleId = await this.orm.call('sign.template', 'create_item_and_role', [this.state.selectedDocumentId, name]);
        const colorId = this.getNextColor();
        this.state.signers.push({
            'id': this.state.nextId,
            'name': name,
            'roleId': roleId,
            'colorId': colorId,
            'isCollapsed': false,
            'itemsCount': 0,
            'isInputFocused': true,
        });
        this.updateCollapse(this.state.nextId, false);
        this.state.documents.forEach(document => {
            document.iframe.setRoleColor(roleId, colorId)
            setTimeout(() => document.iframe.setupDragAndDrop(), 50);
        });
        this.state.nextId++;
    }

    updateCollapse(id, value) {
        /* Make the signer with the matching id receive the new value,
        and force all other signers to have its dropdown collapsed. */
        this.state.signers.forEach(signer => {
            if (signer.id === id) {
                signer.isCollapsed = value;
            } else {
                signer.isCollapsed = true;
                signer.isInputFocused = false;
            }
        });
    }

    getNextColor() {
        const colors = this.state.signers.map(signer => signer.colorId);
        for (let i = 0; i < 55; i++) {
            if (!colors.includes(i)) {
                return i;
            }
        }
        return 0;
    }

    async updateDocuments() {
        const documents = await this.orm.call("sign.document", "search_read", [[["template_id", "=", this.templateID]]]);
        const new_documents = documents.filter((document) => !this.state.documentIds.includes(document.id));
        new_documents.forEach((document) => {
            this.state.documentIds.push(document.id)
            document.attachment_location = `/web/content/${document.attachment_id[0]}`;
            document.iframe = undefined;
            document.setIframe = (iframe) => {
                document.iframe = iframe;
                document.iframe.setFont(this.font);
                this.state.signers.forEach(signer => {
                    document.iframe.setRoleColor(signer.roleId, signer.colorId);
                });
                this.signStatus.save = async () => {
                    const saveDocuments = this.state.documents.filter((document) => !document.deleted).map(document => document.iframe?.saveChangesOnBackend());
                    // Wait for all save operations to complete
                    return Promise.all(saveDocuments);
                };
            };
            this.state.documents.push(document);
        });
    }

    _getTemplateFields() {
        return [
            "id",
            "has_sign_requests",
            "responsible_count",
            "display_name",
            "active",
            "model_name",
        ];
    }

    async fetchTemplateData() {
        const template = await this.orm.call("sign.template", "read", [
            [this.templateID],
            this._getTemplateFields(),
        ]);

        if (!template.length) {
            this.templateID = undefined;
            this.notification.add(_t("The template doesn't exist anymore."), {
                type: "warning",
            });
            return;
        }
        this.state.documents = await this.orm.call("sign.document", "search_read", [[["template_id", "=", this.templateID]]]);
        this.state.documentIds = this.state.documents.map(document => document.id);
        this.state.selectedDocumentId = this.state.documentIds[0];
        this.state.documents.forEach((document) => {
            document.attachment_location = `/web/content/${document.attachment_id[0]}`;
            document.iframe = undefined;
            document.setIframe = (iframe) => {
                document.iframe = iframe;
                if (document.id === this.state.selectedDocumentId) {
                    document.iframe.setIsActive(true);
                }
            };
        });
        this.signTemplate = template[0];
        this.hasSignRequests = this.signTemplate.has_sign_requests;
        this.responsibleCount = this.signTemplate.responsible_count;

        return Promise.all([
            this.fetchSignItemData(),
            this.fetchSignItemTypes(),
            this.fetchSignRoles(),
        ]);
    }

    async fetchFont() {
        const fonts = await rpc("/web/sign/get_fonts/LaBelleAurore-Regular.ttf");
        this.font = fonts[0];
    }

    async fetchSignItemTypes() {
        let domain = [];
        let modelName = this.signTemplate.model_name;
        if (this.referenceDoc && !modelName) {
            modelName = this.referenceDoc.split(',')[0];
        }
        if (modelName) {
            domain = ['|', ['model_name', '=', false], ['model_name', 'in', [modelName, 'res.partner']]];
        }
        this.signItemTypes = await this.orm.call("sign.item.type", "search_read", [domain], {
            context: {
                ...user.context,
                active_test: false,
            },
        });
    }

    async fetchSignRoles() {
        this.signRoles = await this.orm.call("sign.item.role", "search_read", [], {
            context: user.context,
        });
    }

    async fetchSignItemData() {
        this.signItemOptions = await this.orm.call(
            "sign.item.option",
            "search_read",
            [[], ["id", "value"]],
            { context: user.context }
        );
    }

    /**
     * Checks that user has group sign.manage_template_access for showing extra fields
     */
    async checkManageTemplateAccess() {
        this.manageTemplateAccess = await user.hasGroup("sign.manage_template_access");
    }

    goBackToKanban() {
        return this.action.doAction("sign.sign_template_action", { clearBreadcrumbs: true });
    }

    async onTemplateSaveClick() {
        const templateId = this.signTemplate.id;
        this.state.properties = await this.orm.call("sign.template", "write", [[templateId], { active: true }]);
        this.signTemplate.active = true;
        this.notification.add(_t("Document saved as Template."), { type: "success" });
        return this.state.properties;
    }

    getSignTemplateBodyProps(documentId) {
        const document = this.state.documents.find((doc) => doc.id === documentId);
        return {
            attachmentLocation: document.attachment_location,
            manageTemplateAccess: this.manageTemplateAccess,
            hasSignRequests: this.hasSignRequests,
            signTemplate: this.signTemplate,
            signItemTypes: this.signItemTypes,
            signItems: this.signItems,
            signRoles: this.signRoles,
            radioSets: this.radioSets,
            signItemOptions: this.signItemOptions,
            goBackToKanban: () => this.goBackToKanban(),
            resModel: this.resModel,
            signStatus: this.signStatus,
            iframe: document.iframe,
            setIframe: (iframe) => document.setIframe(iframe),
            onTemplateSaveClick: () => this.onTemplateSaveClick(),
            documentId: documentId,
            updateSignItemsCountCallback: () => this.updateSignItemsCount(),
        }
    }

    updateSelectedDocument(documentId) {
        this.state.documents.find((doc) => doc.id === this.state.selectedDocumentId).iframe?.setIsActive(false);
        this.state.selectedDocumentId = documentId;
        this.state.documents.find((doc) => doc.id === this.state.selectedDocumentId).iframe?.setIsActive(true);
    }

    async updateDocumentName(documentId, newName) {
        let document = this.state.documents.find((doc) => doc.id === documentId);
        if (document && newName !== document.display_name) {
            document.display_name = newName;
            await this.orm.write(
                "sign.document",
                [documentId],
                { name: newName }
            );
        }
    }

    async deleteDocument(documentId) {
        if (this.state.documents.length === 1) {
            return;
        }
        if (this.state.selectedDocumentId === documentId) {
            this.updateSelectedDocument(this.getNewFocusedDocument(documentId).id);
        }
        const document = this.state.documents.find((doc) => doc.id === documentId);
        document.deleted = true;
        await this.orm.unlink("sign.document", [documentId]);
    }

    /**
     *
     * @param {Number} documentId
     * @param {Number} direction
     * Moves the document up (direction = -1) or down (direction = 1) in the list of documents,
     * by swapping the sequence numbers of the two documents.
     */
    async moveDocument (documentId, direction) {
        const active_documents = this.state.documents.filter((doc) => !doc.deleted).sort((a, b) => a.sequence - b.sequence);
        const index_1 = active_documents.findIndex(doc => doc.id === documentId);
        const index_2 = index_1 + direction;
        if (index_2 < 0 || index_2 >= active_documents.length) {
            return;
        }
        const document_a = active_documents[index_1];
        const document_b = active_documents[index_2];
        const seq_a = document_a.sequence;
        const seq_b = document_b.sequence;
        document_a.sequence = seq_b;
        document_b.sequence = seq_a;
        await this.orm.write("sign.document", [document_a.id], { sequence: seq_b });
        await this.orm.write("sign.document", [document_b.id], { sequence: seq_a });
    }

    getNewFocusedDocument(oldFocusedDocumentId) {
        return this.state.documents.find((doc) => doc.id !== oldFocusedDocumentId && !doc.deleted);
    }

    async showConfirmationDialog(){
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirmation"),
                body: _t("Your changes will be discarded. Would you like to save them as a template?"),
                confirm: async () => {
                    await this.onTemplateSaveClick();
                    if (this.signStatus.isTemplateChanged) {
                        // If there is unsaved sign items, it will save the template before leaving.
                        await this.signStatus.save();
                    }
                    resolve(true);
                },
                confirmLabel: _t("Save & close"),
                cancel: () => {
                    resolve(true);
                },
                cancelLabel: _t("Discard"),
                dismiss: () => {
                    resolve(false);
                }
            });
        });
    }

    async onUpdateDocument(documentId, file) {
        /* Update document by duplicating and archiving the current template. */
        new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Update Document"),
                body: _t(
                    "Updating a document generates a new template with the same sign items. " +
                    "The copied items will land in the same coordinates as their originals if the " +
                    "number of pages match with the previous PDF. Do you want to proceed?"
                ),
                confirmLabel: _t("Update Document"),
                confirm: () => resolve(true),
                cancelLabel: _t("Discard"),
                cancel: () => resolve(false),
                dismiss: () => resolve(false),
            });
        }).then(async (confirmed) => {
            if (!confirmed)
                return;
            const action = await this.orm.call(
                "sign.template",
                "update_document",
                [[this.signTemplate.id], documentId, file]
            );
            this.action.doAction(action, { clearBreadcrumbs: true });
        });
    }
}

registry.category("actions").add("sign.Template", SignTemplate);
