import { Plugin } from "@html_editor/plugin";

export class SignatureInputPlugin extends Plugin {
    static id = "signatureInput";
    static dependencies = ["baseContainer", "history"];
    resources = {
        mount_component_handlers: this.setupNewSignatureInput.bind(this),
    };
    setupNewSignatureInput({ name, props }) {
        if (name !== "signatureInput") {
            return;
        }
        Object.assign(props, {
            replaceSignatureInputWithImage: (host, b64SignatureImage) => {
                if (!host.isConnected) {
                    return;
                }
                const baseContainer = this.dependencies.baseContainer.createBaseContainer();
                const img = document.createElement("img");
                img.classList.add("img", "img-fluid", "o_we_custom_image");
                img.style = "width: 50%";
                img.src = b64SignatureImage;
                baseContainer.append(img);
                host.replaceWith(baseContainer);
                this.dependencies.history.addStep();
            },
        });
    }
}
