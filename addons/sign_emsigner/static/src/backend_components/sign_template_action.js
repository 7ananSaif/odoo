import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SignTemplate } from "@sign/backend_components/sign_template/sign_template_action";
import { SignTemplateSidebar } from "@sign/backend_components/sign_template/sign_template_sidebar";
import { SignTemplateSidebarRoleItems } from "@sign/backend_components/sign_template/sign_template_sidebar_role_items";

export function getEmsignerRole() {
    return {
        async getEmsignerRoleValues(props){
            const roleIds = props.signers.map(signer => signer.roleId);
            return {
                emSignerRole: await this.orm.searchCount(
                    "sign.item.role",
                    [
                        ["id", "in", roleIds],
                        ["auth_method", "=", "emsigner"]
                    ],
                ),
                hasDocument: props.documents.filter(doc => !doc.deleted).length > 1 }
        },
    }
}

patch(SignTemplate.prototype, {
    setup() {
        super.setup();
        const functions = getEmsignerRole();
        Object.assign(this, functions);
    },

    async updateDocuments() {
        await super.updateDocuments();
        const emsignerRoleValues = await this.getEmsignerRoleValues(this.state);
        await this._checkEmsignerUserWarning((emsignerRoleValues.hasDocument && emsignerRoleValues.emSignerRole > 0) || emsignerRoleValues.emSignerRole > 1);
    },

    async _checkEmsignerUserWarning(showEmsignerWarning = false) {
        if (!this.state.signers || this.state.signers.length === 0)
            return;

        if (showEmsignerWarning) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Warning"),
                body: _t("Aadhaar Sign works only with a single signer and document. Adding more will switch to the standard eSignature."),
                confirmLabel: _t("Ok"),
            });
        }
    }
});

patch(SignTemplateSidebar.prototype, {
    setup() {
        super.setup();
        this.emsignerState = useState({
            showAddDocumentBtn: true,
        });
    },

    displayAddDocumentButton(value) {
        this.emsignerState.showAddDocumentBtn = value;
    },

    getSidebarRoleItemsProps(id) {
        return {
            ...super.getSidebarRoleItemsProps(id),
            propsForEmsigner: this.props,
            displayAddDocumentButton: (value) => this.displayAddDocumentButton(value),
        };
    }
});

patch(SignTemplateSidebarRoleItems, {
    props: {
        ...SignTemplateSidebarRoleItems.props,
        propsForEmsigner: { type: Object, optional: true },
        displayAddDocumentButton: { type: Function, optional: true },
    }
});


patch(SignTemplateSidebarRoleItems.prototype, {

    setup() {
        super.setup();
        const functions = getEmsignerRole();
        Object.assign(this, functions);

        if (this.props.propsForEmsigner.signers.length > 0) {
            this.getEmsignerRoleValues(this.props.propsForEmsigner)
            .then((result) => {
                this.props.displayAddDocumentButton(result.emSignerRole > 0);
            })
        };
    },

    async openSignRoleRecord() {
        this.dialog.add(FormViewDialog, {
            resId: this.props.roleId,
            resModel: "sign.item.role",
            size: "md",
            title: _t("Signer Edition"),
            onRecordSaved: async ({ data }) => {
                this.state.roleName = data.name;
                await this.updateRoleNameAndAvatar(data);
                const emsignerRoleValues = await this.getEmsignerRoleValues(this.props.propsForEmsigner);
                // Show warning if the role is emsigner and there are multiple signers or documents
                if ((emsignerRoleValues.hasDocument && emsignerRoleValues.emSignerRole > 0) || emsignerRoleValues.emSignerRole > 1) {
                    this.dialog.add(ConfirmationDialog, {
                        title: _t("Warning"),
                        body: _t("Aadhaar Sign works only with a single signer and document. Adding more will switch to the standard eSignature."),
                        confirmLabel: _t("Ok"),
                    });
                }
                this.props.displayAddDocumentButton(emsignerRoleValues.emSignerRole > 0);
            },
        });
    }
});
