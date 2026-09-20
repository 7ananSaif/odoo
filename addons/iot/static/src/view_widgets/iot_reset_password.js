import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";

export class IoTResetPassword extends Component {
    static template = `iot.HeaderButton`;
    static props = {
        ...standardWidgetProps,
        btn_name: { type: String },
        btn_class: { type: String },
    };

    setup() {
        super.setup();
        this.longpolling = useService("iot_longpolling");
        this.notification = useService("notification");
    }

    get ip() {
        return this.props.record.data.ip;
    }

    get name() {
        return this.props.record.data.name;
    }

    async onClick() {
        try {
            const response = await this.longpolling.action(this.ip, null, null, false, "/iot_drivers/generate_password");
            if (!response?.result?.password) {
                return this.doWarnFail();
            }
            this.notification.add(response.result.password, {
                type: "info",
                title: _t("New SSH password for %s", this.name),
            });
        } catch (error) {
            console.error(error);
        }
    }

    doWarnFail() {
        this.notification.add(_t("Failed to reset %s password.", this.name), { type: "danger" });
    }
}

export const ioTResetPassword = {
    component: IoTResetPassword,
    extractProps: ({ attrs }) => {
        return {
            btn_name: attrs.btn_name,
            btn_class: attrs.btn_class,
        };
    },
};
registry.category("view_widgets").add("iot_reset_password", ioTResetPassword);
