import { Component, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ThankYouDialog } from "./thank_you_dialog";
import { user } from "@web/core/user";

export class SignRefusalDialog extends Component {
    static template = "sign.SignRefusalDialog";
    static components = {
        Dialog,
    };
    static props = {
        close: Function,
    };

    setup() {
        this.refuseNameEl = useRef("refuse-name");
        this.refuseEmailEl = useRef("refuse-email");
        this.refuseReasonEl = useRef("refuse-reason");
        this.refuseButton = useRef("refuse-button");
        this.dialog = useService("dialog");
        this.signInfo = useService("signInfo");
        this.user = user.userId;
        this.isPublicUser = !this.user;
    }

    get dialogProps() {
        return {
            size: "md",
            title: _t("Decline to sign"),
        };
    }

    checkForChanges() {
        const refusal = {
            reason: this.refuseReasonEl.el.value.trim(),
            name: this.isPublicUser && this.refuseNameEl.el.value.trim(),
            email: this.isPublicUser && this.refuseEmailEl.el.value.trim(),
        }
        const isRefusalReasonEmpty = refusal.reason.length === 0;
        const isPublicUserUnindentified = this.isPublicUser && (!refusal.name || !refusal.email);

        this.refuseButton.el.disabled = isRefusalReasonEmpty || isPublicUserUnindentified;
    }

    async refuse() {
        const reason = this.refuseReasonEl.el.value;
        const route = `/sign/refuse/${this.signInfo.get("documentId")}/${this.signInfo.get(
            "signRequestItemToken"
        )}`;
        let params = {
            refusal_reason: reason,
        };

        // When not logged in, add name and email of the public user.
        if (!this.user) {
            const name = this.refuseNameEl.el.value;
            const email = this.refuseEmailEl.el.value;
            params = {
                ...params,
                refusal_name: name,
                refusal_email: email,
            }
        }

        const response = await rpc(route, params);
        if (!response) {
            this.dialog.add(
                AlertDialog,
                {
                    body: _t("Sorry, you cannot refuse this document"),
                },
                {
                    onClose: () => window.location.reload(),
                }
            );
        }
        this.dialog.add(SignRefusalDialogTitle);

        this.props.close();
    }
}

export class SignRefusalDialogTitle extends ThankYouDialog {
    static template = "sign.SignRefusalDialogTitle";
    setup() {
        super.setup();
        this.message = this.props.message || _t("Document refusal submitted.");
        this.dialog = useService("dialog");
        this.props.isRefused = true;
    }
}
