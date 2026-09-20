import { registry } from "@web/core/registry";
import { Document } from "@sign/components/sign_request/document_signable";
import { SignRequest } from "@sign/backend_components/sign_request/sign_request_action";
import { useSubEnv, EventBus } from "@odoo/owl";
import { SignableRequestControlPanel } from "@sign/backend_components/sign_request/signable_sign_request_control_panel";
import { SignablePDFIframe } from "@sign/components/sign_request/signable_PDF_iframe";


export class SignableSignRequest extends SignRequest {
    static components = {
        ...SignableSignRequest.components,
        Document: Document,
        SignRequestControlPanel: SignableRequestControlPanel,
    };
    setup() {
        super.setup();
        this.signInfo.set({
            tokenList: this.tokenList,
            nameList: this.nameList,
        });
        useSubEnv({
            editWhileSigningBus: new EventBus(),
        });
    }

    get nameList() {
        return this.props.action.context.name_list;
    }

    get tokenList() {
        return this.props.action.context.token_list;
    }

    get documentProps() {
        return {
            ...super.documentProps,
            PDFIframeClass: SignablePDFIframe,
        };
    }
}

registry.category("actions").add("sign.SignableDocument", SignableSignRequest);
