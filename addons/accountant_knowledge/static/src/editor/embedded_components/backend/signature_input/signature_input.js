import { Component } from "@odoo/owl";
import { getEmbeddedProps } from "@html_editor/others/embedded_component_utils";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { SignNameAndSignatureDialog } from "@sign/dialogs/dialogs";

export class SignatureInputComponent extends Component {
    static template = "accountant_knowledge.EmbeddedSignatureInput";
    static props = {
        host: { type: Object },
        replaceSignatureInputWithImage: Function,
    };

    setup() {
        this.dialog = useService("dialog");
    }

    openSignatureDialog() {
        const signature = { name: user.name };
        const close = this.dialog.add(SignNameAndSignatureDialog, {
            signature,
            activeFrame: true,
            frame: {},
            hash: "",
            displaySignatureRatio: 3,
            onConfirm: () => {
                this.props.replaceSignatureInputWithImage(
                    this.props.host,
                    signature.getSignatureImage()
                );
                close();
            },
        });
    }
}

export const signatureInputEmbedding = {
    name: "signatureInput",
    Component: SignatureInputComponent,
    getProps: (host) => ({ host, ...getEmbeddedProps(host) }),
};
