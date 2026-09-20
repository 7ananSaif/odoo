import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { Component, useEffect, useComponent, markup } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { SignRequestDocumentsDropdown } from "@sign/backend_components/sign_request/sign_request_documents_dropdown";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import multiFileUpload from "@sign/backend_components/multi_file_upload";

function useResendButtons() {
    const component = useComponent();
    const onClickResend = async (e) => {
        const parent = e.currentTarget.parentNode;
        const signRequestItemId = parseInt(parent.dataset.id);
        await component.orm.call(
            "sign.request.item",
            "send_signature_accesses",
            [signRequestItemId],
            { context: user.context }
        );
        e.target.innerText = _t("Resent!");
    };
    useEffect(
        (showResendButtons) => {
            if (!showResendButtons) {
                return;
            }
            const status = document.querySelector("div.signer-status");
            const signerNames = status.querySelectorAll(
                ".o_sign_signer_status.o_sign_signer_waiting"
            );
            const sequencedSignatureMailSentOrderSet = component.signInfo.get("sequencedSignatureMail");
            Array.from(signerNames).forEach((signerNameEl) => {
                signerNameEl.style.display = "flex";
                signerNameEl.style.alignItems = "flex-end";
                if (!sequencedSignatureMailSentOrderSet){
                    const requestItemStates = component.signInfo.get("requestItemStates") || {};
                    const stateSet = requestItemStates[signerNameEl.dataset.id];
                    const text = stateSet ? _t("Resend") : _t("Send");
                    const title = stateSet ? _t("Resend the invitation") : _t("Send the invitation");
                    const button = document.createElement("button");
                    button.title = title;
                    button.innerText = text;
                    button.className = "o_sign_resend_access_button btn btn-link ms-2 me-2";
                    signerNameEl.appendChild(button);
                    button.addEventListener("click", onClickResend);
                }
            });
        },
        () => [component.showResendButtons]
    );
}

export class SignRequestControlPanel extends Component {
    static template = "sign.SignRequestControlPanel";
    static components = {
        ControlPanel,
        Dropdown,
        DropdownItem,
        SignRequestDocumentsDropdown,
    };
    static props = {
        signerStatus: {
            type: Object,
            optional: true,
        },
        goBackToKanban: { type: Function },
    };

    setup() {
        this.controlPanelDisplay = {};
        this.action = useService("action");
        this.orm = useService("orm");
        this.signInfo = useService("signInfo");
        this.nextTemplate = multiFileUpload.getNext();
        useResendButtons();
        this.addDialog = useOwnedDialogs();
    }

    get markupSignerStatus() {
        return markup(this.props.signerStatus.innerHTML);
    }

    get showResendButtons() {
        const documentSent = this.signInfo.get("signRequestState") === "sent";
        const isAuthor = this.signInfo.get("createUid") === user.userId;
        return isAuthor && documentSent;
    }

    get allowCancel() {
        const needToSign = this.signInfo.get("needToSign");
        const state = this.signInfo.get("signRequestState");
        return needToSign && !["signed", "canceled"].includes(state);
    }

    // In a normal OWL context, this property ensures the dropdown renders fine.
    // However, in a signing session, the template is used statically and JS is not available
    // so this will be undefined and the component won't render which is needed.
    get shouldShowDownloadDropdown() {
        return true;
    }

    async signDocument() {
        const action = await this.orm.call("sign.request", "go_to_signable_document", [
            [this.signInfo.get("documentId")],
        ]);
        action.name = _t("Sign");
        this.action.doAction(action);
    }

    async cancelDocument() {
        this.addDialog(ConfirmationDialog, {
            body: _t("Are you sure you want to cancel this sign request?"),
            confirm: async () => {
                await this.orm.call("sign.request", "cancel", [this.signInfo.get("documentId")]);
                const result = await this.orm.call(
                    "sign.request",
                    "get_close_values",
                    [[this.signInfo.get("documentId")]],
                );
                const context = result.custom_action ? {} : { clearBreadcrumbs: true };
                this.env.services.action.doAction(result.action, context);
            },
            cancel: () => {},
        });
    }

    async goToNextDocument() {
        const templateName = this.nextTemplate.name;
        const templateId = parseInt(this.nextTemplate.template);
        multiFileUpload.removeFile(this.nextTemplate.template);
        await this.action.doAction(
            {
                type: "ir.actions.client",
                tag: "sign.Template",
                name: _t("Template %s", templateName),
                params: {
                    sign_edit_call: "sign_send_request",
                    id: templateId,
                    sign_directly_without_mail: false,
                },
            },
            { clear_breadcrumbs: true }
        );
    }
}
