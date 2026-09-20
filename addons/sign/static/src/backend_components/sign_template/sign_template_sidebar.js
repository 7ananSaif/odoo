import { Component, onWillUpdateProps, useState } from "@odoo/owl";
import { SignTemplateSidebarRoleItems } from "./sign_template_sidebar_role_items";
import { useService } from "@web/core/utils/hooks";
import { useSignViewButtons } from "@sign/views/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { getDataURLFromFile } from "@web/core/utils/urls";

export class SignTemplateSidebar extends Component {
    static template = "sign.SignTemplateSidebar";
    static components = {
        SignTemplateSidebarRoleItems,
        Dropdown,
        DropdownItem,
    };
    static props = {
        signItemTypes: { type: Array },
        isSignRequest: { type: Boolean },
        signTemplateId: { type: Number },
        updateRoleName: { type: Function },
        signers: { type: Array },
        hasSignRequests: { type: Boolean },
        updateDocumentName: { type: Function },
        updateSigners: { type: Function },
        pushNewSigner: { type: Function },
        updateCollapse: { type: Function },
        deleteRole: { type: Function },
        documents: { type: Array },
        selectedDocumentId: { type: Number },
        updateSelectedDocument: { type: Function },
        updateDocuments: { type: Function },
        deleteDocument: { type: Function },
        moveDocumentUp: { type: Function },
        moveDocumentDown: { type: Function },
        onEditTemplate: { type: Function },
        onUpdateDocument: { type: Function },
        saveManually: { type: Function },
    };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            editableDocumentId: false,
        });
        const functions = useSignViewButtons(this.props.signTemplateId);
        Object.assign(this, functions);
        onWillUpdateProps(() => this.updateSignerNames(this.props.signers));
    }

    focusOnNewAddedSigner(roleId) {
        const spanSelector = `span[data-role-id="${roleId}"]`;
        const inputSelector = `input[data-role-id="${roleId}"]`;

        // Polling function to check if the input is available in the DOM
        const checkInput = () => {
            const span = document.querySelector(spanSelector);
            const input = document.querySelector(inputSelector);

            // If the span and input are found, focus on input
            if (span && input) {
                span.click();
                input.focus();
                input.select();
            } else {
                // If input is not found, wait for the next frame and check again
                requestAnimationFrame(checkInput);
            }
        };

        checkInput();
    }

    async onClickAddSigner() {
        await this.props.pushNewSigner();
        this.focusOnNewAddedSigner(this.props.signers.at(-1).roleId);
    }

    deleteSigner(signerId, roleId) {
        const updatedSigners = [...this.props.signers].filter(signer => signer.id != signerId);

        this.updateSignerNames(updatedSigners);
        /* After deleting the signer, if no signer is focused, focus the last one in the array. */
        if (!updatedSigners.some(signer => !signer.isCollapsed) && updatedSigners.length > 0)
            updatedSigners[updatedSigners.length - 1].isCollapsed = false;

        this.props.updateSigners(updatedSigners);
        this.props.deleteRole(roleId);
    }

    updateSignerNames(signers) {
        let signer_idx = 1;
        const str = _t("Signer")
        for (const signer of signers) {
            if (signer.name.includes(str)) {
                signer.name = _t("Signer %s", signer_idx);
                this.props.updateRoleName(signer.roleId, signer.name);
            }
            signer_idx++;
        }
    }

    getSidebarRoleItemsProps(id) {
        //  TODO MASTER: we should put the role name here. it would prevent one rpc per role...
        const signer = this.props.signers.find(signer => signer.id === id);
        return {
            id: id,
            name: signer.name,
            signTemplateId: this.props.signTemplateId,
            roleId: signer.roleId,
            colorId: signer.colorId,
            signItemTypes: this.props.signItemTypes,
            isSignRequest: this.props.isSignRequest,
            updateRoleName: this.props.updateRoleName,
            isCollapsed: signer.isCollapsed,
            isInputFocused: signer.isInputFocused,
            /* Update callbacks binding for parent props: */
            updateCollapse: (id, value) => this.props.updateCollapse(id, value),
            onDelete: () => this.deleteSigner(id, signer.roleId),
            onFieldNameInputKeyUp: (ev) => this.onFieldNameInputKeyUp(ev),
            itemsCount: signer.itemsCount,
            hasSignRequests: this.props.hasSignRequests,
            assignTo: signer.assignTo,
        };
    }

    onDocumentNameBlur() {
        this.state.editableDocumentId = false;
    }

    onFieldNameInputKeyUp(ev) {
        if (ev.key === "Enter") {
            ev.target.blur();
        }
    }

    onUpdateSelectedDocument(documentId) {
        this.props.updateSelectedDocument(documentId);
    }

    onDocumentNameChanged(documentId, e) {
        const documentName = e.target.value;
        if (documentName) {
            this.props.updateDocumentName(documentId, documentName);
        }
    }

    setEditableDocumentId (documentId) {
        this.state.editableDocumentId = documentId;
        this.props.updateSelectedDocument(documentId);
    }

    onDocumentNameTextClick(documentId) {
        this.state.editableDocumentId = documentId;
        const input = document.querySelector(`[data-document-id="${documentId}"]`);

        // Polling function to check if the input is no longer `d-none`
        const waitForVisibility = () => {
            if (input && !input.classList.contains('d-none')) {
                // Input is visible, so we can focus
                input.focus();
                input.select();
            } else {
                // Input is still hidden, keep checking in the next frame
                requestAnimationFrame(waitForVisibility);

            }
        };

        waitForVisibility();
    }

    async onRemoveDocument(documentId) {
        await this.props.deleteDocument(documentId);
        this.render();
    }

    async onMoveDocumentUp(documentId) {
        await this.props.moveDocumentUp(documentId);
        this.render();
    }

    async onMoveDocumentDown(documentId) {
        await this.props.moveDocumentDown(documentId);
        this.render();
    }

    async onUpdateDocument(documentId, ev) {
        /* Check if pdf got uploaded, save manually, and call update document function from props. */
        const file = ev.target.files && ev.target.files.length && ev.target.files[0];
        if (!file)
            return;
        if (this.props.saveManually) {
            await this.props.saveManually();
        }
        const url = await getDataURLFromFile(file);
        const fileData = {
            name: file.name,
            datas: url.split(",")[1],
        };
        await this.props.onUpdateDocument(documentId, fileData);
    }

}
