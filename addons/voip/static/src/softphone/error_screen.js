import { Component } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class ErrorScreen extends Component {
    static defaultProps = { title: _t("Something went wrong 😵‍💫"), isNonBlocking: false };
    static props = {
        title: { type: String, optional: true },
        isNonBlocking: { type: Boolean, optional: true },
        message: String,
        button: {
            type: Object,
            shape: {
                callback: Function,
                text: String,
            },
            optional: true,
        },
    };
    static template = "voip.ErrorScreen";

    setup() {
        this.voip = useService("voip");
    }

    onClick() {
        if (this.props.isNonBlocking) {
            this.voip.resolveError();
        }
    }
}
