import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { Document } from "@sign/components/sign_request/document_signable";
import { SignablePDFIframe } from "@sign/components/sign_request/signable_PDF_iframe";
import { EmsignerDialog } from "@sign_emsigner/dialogs/emsigner_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";


patch(SignablePDFIframe.prototype, {
    postRender() {
        const res = super.postRender();
        const errorCode = this.props.errorMessage;
        if (errorCode) {
            const [errorMessage] = processErrorMessage.call(this, errorCode);
            this.dialog.add(
                AlertDialog,
                {
                    title: _t("Error"),
                    body: errorMessage,
                },
                {
                    onClose: () => {
                        deleteQueryParamFromURL("error_message");
                    },
                }
            );
        }
        if (this.props.showThankYouDialog) {
            this.props.openThankYouDialog();
        }
        return res;
    },
});

patch(Document.prototype, {

    async getAuthDialog() {
        if (this.authMethod === "emsigner") {
            const credits = await rpc("/emsigner/has_emsigner_credits");
            if (credits) {
                const [route, params] = await this._getRouteAndParams();
                params.signatureInfo = this.signatureInfo.signatureValues;
                return {
                    component: EmsignerDialog,
                    props: {
                        route,
                        params,
                        onSuccess: () => {
                            this.openThankYouDialog();
                        },
                    },
                };
            }
        }
        return super.getAuthDialog();
    },

    getDataFromHTML() {
        super.getDataFromHTML();
        const { el: parentEl } = this.props.parent;
        this.showThankYouDialog = Boolean(
            parentEl.querySelector("#o_sign_show_emsigner_thank_you_dialog")
        );
        this.errorMessage = parentEl.querySelector("#o_emsigner_show_error_message")?.value;
    },

    getIframeProps(sign_document_id) {
        const props = super.getIframeProps(sign_document_id);
        return {
            ...props,
            showThankYouDialog: this.showThankYouDialog,
            errorMessage: this.errorMessage,
            openThankYouDialog: () => this.openThankYouDialog(),
        };
    },
}
);

function deleteQueryParamFromURL(param) {
    const url = new URL(location.href);
    url.searchParams.delete(param);
    window.history.replaceState(null, "", url);
}

/**
 * Processes special errors from the IAP server
 * @param { String } errorMessage
 * @returns { [String, Boolean] } error message, title or false
 */
function processErrorMessage(errorMessage) {
    const errorMap = {
        err_connection_odoo_instance: [
            _t(
                "The emSigner identification data could not be forwarded to Odoo, the signature could not be saved."
            ),
        ],
    };
    return errorMap[errorMessage] ? errorMap[errorMessage] : [errorMessage];
}
