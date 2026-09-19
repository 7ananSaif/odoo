import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";

export class IoTRestartOdoo extends Component {
    static template = `iot.HeaderButton`;
    static props = {
        ...standardWidgetProps,
        btn_name: { type: String },
        btn_class: { type: String },
    };

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.iotHttpService = useService("iot_http");
        this.notification = useService("notification");
    }

    async onClick() {
        this.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure you want to restart Odoo on the IoT Box?"),
            confirm: this.restartOdoo.bind(this),
            cancel: () => {},
        });
    }

    restartOdoo() {
        const { identifier, name } = this.props.record.data;
        this.iotHttpService.action(
            this.props.record._config.resId,
            identifier,
            { action: "restart_odoo" },
            () => this.notification.add(_t("%s is currently restarting", name), {
                type: "info",
            }),
            () => {
                this.notification.add(
                    _t("Failed to send the restart command to the IoT Box ('%s')", name), { type: "danger" }
                )
            },
        );
    }
}

export const ioTRestartOdoo = {
    component: IoTRestartOdoo,
    extractProps: ({ attrs }) => {
        return {
            btn_name: attrs.btn_name,
            btn_class: attrs.btn_class,
        };
    },
};
registry.category("view_widgets").add("iot_restart_odoo", ioTRestartOdoo);
