import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class IoTRemoteDebug extends Component {
    static template = `iot.HeaderButton`;
    static props = {
        ...standardWidgetProps,
        btn_name: { type: String },
        btn_class: { type: String },
    };

    setup() {
        super.setup();
        this.iotHttp = useService("iot_http");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.state = useState({ enabled: false });

        // Get ngrok status on view load
        this.iotHttp.websocket.onMessage(this.identifier, null, this.onMessageUpdateStatus.bind(this));
        this.iotHttp.websocket.sendMessage(this.identifier, { 'status': true }, null, 'remote_debug');
    }

    get identifier() {
        return this.props.record.data.identifier;
    }

    async onClick() {
        this.dialog.add(TokenDialog, {
            validate: this.enableRemoteDebug.bind(this),
            enabled: this.state.enabled,
        });
    }

    async enableRemoteDebug(token) {
        this.iotHttp.websocket.onMessage(
            this.identifier,
            null,
            (message) => {
                this.onMessageUpdateStatus(message);
                if (token && !this.state.enabled) {
                    return this.onFailure();
                }
                this.notification.add(
                    _t("Remote debug is %s.", this.state.enabled ? _t("enabled") : _t("disabled")), {
                        type: "info",
                    }
                );
            },
            this.onFailure.bind(this),
        );
        this.iotHttp.websocket.sendMessage(this.identifier, { token }, null, "remote_debug");
    }

    onMessageUpdateStatus(message) {
        this.state.enabled = message.result?.enabled;
    }

    onFailure() {
        this.notification.add(_t("Failed to toggle remote debug."), {
            type: "danger",
        });
    }
}

export const ioTRemoteDebug = {
    component: IoTRemoteDebug,
    extractProps: ({ attrs }) => {
        return {
            btn_name: attrs.btn_name,
            btn_class: attrs.btn_class,
        };
    },
};

export class TokenDialog extends Component {
    static template = "iot.RemoteDebugDialog";
    static components = { Dialog };
    static props = {
        validate: Function,
        close: Function,
        enabled: Boolean,
    };

    setup() {
        this.state = useState({ token: "" });
    }

    validate() {
        this.props.validate(this.state.token);
        this.props.close();
    }
}

registry.category("view_widgets").add("iot_remote_debug", ioTRemoteDebug);
