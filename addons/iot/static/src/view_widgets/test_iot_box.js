import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { uuid } from "@web/core/utils/strings";
import { _t } from '@web/core/l10n/translation';
import { Component } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

export class TestIotBox extends Component {
    static template = `iot.HeaderButton`;
    static props = {
        ...standardWidgetProps,
        btn_name: { type: String },
        btn_class: { type: String },
    };

    setup() {
        super.setup();
        this.notification = useService('notification');
        this.iotHttpService = useService('iot_http');
    }

    async onClick() {
        const { ip, identifier } = this.props.record.data;
        const requestId = uuid();
        this.completeSuccess = true;
        const failureCallback = (protocol) => {
            this.notification.add(_t("Communication protocol '%s' is not working properly.", protocol), {
                type: 'danger'
            });
            this.completeSuccess = false;
        }

        this.removeTestingNotification = this.notification.add(
            _t("Testing communication with IoT Box and network quality, please wait..."),
            {
                type: 'info',
                autocloseDelay: 30000,
            }
        );

        // Check webRTC
        try {
            await this.iotHttpService.webRtc.onMessage(identifier, identifier, requestId, () => {}, () => {
                failureCallback("WebRTC");
            });
            await this.iotHttpService.webRtc.sendMessage(identifier, {}, requestId, "test_protocol");
        } catch {
            // Catch connection timeout (not going through onFailure)
            failureCallback("WebRTC");
        }

        // Check longpolling (no onMessage as we only check if the endpoint is reachable)
        try {
            await this.iotHttpService.longpolling.sendMessage(ip, {
                device_identifier: identifier,
                data: {}
            }, requestId, true);
        } catch {
            failureCallback("Longpolling");
        }

        // Check websocket
        this.iotHttpService.websocket.onMessage(
            identifier,
            identifier,
            this.onConnectionTestSuccess.bind(this),
            () => failureCallback("Websocket"),
            undefined,
            requestId,
        );
        await this.iotHttpService.websocket.sendMessage(identifier, {}, requestId, "test_connection");
    }

    onConnectionTestSuccess(data) {
        this.removeTestingNotification?.();
        if (this.completeSuccess) {
            this.notification.add(_t("All communication protocols are working properly."), { type: 'success' });
        }
        if (!data.result) {
            this.notification.add(
                _t("Failed to check IoT Box network, check that it's connected to the Internet."), {
                    type: 'danger'
                }
            );
            return;
        }

        const { lan_quality, wan_quality } = data.result;
        let type = 'success';
        if (lan_quality === "normal" || wan_quality === "normal") {
            type = 'info';
        }
        if (lan_quality === "slow" || wan_quality === "slow") {
            type = 'warning';
        }
        if (lan_quality === "unreachable" || wan_quality === "unreachable") {
            type = 'danger';
        }

        this.notification.add(
            _t("IoT Box local network is %(lan_quality)s and internet is %(wan_quality)s", {
                lan_quality,
                wan_quality
            }),
            {
                type,
                autocloseDelay: 6000, // display longer to read (= websocket timeout)
            }
        );
    }
}

export const testIotBox = {
    component: TestIotBox,
    extractProps: ({ attrs }) => {
        return {
            btn_name: attrs.btn_name,
            btn_class: attrs.btn_class
        };
    },
};
registry.category("view_widgets").add("test_iot_box", testIotBox);
