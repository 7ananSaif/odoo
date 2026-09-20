import { Component } from "@odoo/owl";
import { addLoadingEffect } from "@web/core/utils/ui";
import { rpc } from "@web/core/network/rpc";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

export class EmsignerDialog extends Component {
    static template = "sign_emsigner.EmsignerDialog";
    static components = {
        Dialog,
    };
    static props = {
        route: String,
        params: Object,
        onSuccess: Function,
        close: Function,
    };

    setup() {
        this.dialog = useService("dialog");
    }

    async onEmsignerClick() {
        const submitEl = document.querySelector(".o_emsigner_submit");
        addLoadingEffect(submitEl);
        const { success, authorization_url, params, message } = await rpc(
            this.props.route,
            this.props.params,
        );
        if (success) {
            if (authorization_url) {
                let form = document.createElement("form");
                form.method = "POST";
                form.action = authorization_url;

                let index = 1;
                for (let key in params) {
                    if (params.hasOwnProperty(key)) {
                        let hiddenField = document.createElement("input");
                        hiddenField.type = "hidden";
                        hiddenField.name = "Parameter" + index; // Naming as Parameter1, Parameter2, etc.
                        hiddenField.value = params[key];
                        form.appendChild(hiddenField);
                        index++;
                    }
                }
                document.body.appendChild(form);
                form.submit();
            } else {
                this.props.onSuccess();
            }
        } else {
            this.dialog.add(
                AlertDialog,
                {
                    body: message,
                },
                {
                    onClose: () => window.location.reload(),
                }
            );
        }
    }
}
