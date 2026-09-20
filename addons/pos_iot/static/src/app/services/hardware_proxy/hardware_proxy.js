import {
    HardwareProxy,
    hardwareProxyService,
} from "@point_of_sale/app/services/hardware_proxy_service";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { IoTPrinter } from "@pos_iot/app/utils/printer/iot_printer";
import { formatEndpoint } from "@iot_base/network_utils/http";

patch(hardwareProxyService, {
    dependencies: [...hardwareProxyService.dependencies, "orm", "iot_http"],
});
patch(HardwareProxy.prototype, {
    setup({ orm, iot_http }) {
        super.setup(...arguments);
        this.iotBoxes = [];
        this.iotHttp = iot_http;
    },
    /**
     * @override
     */
    connectToPrinter() {
        console.log("Connecting to IoT Printer: deviceControllers", this.deviceControllers);
        this.printer = new IoTPrinter({
            device: this.deviceControllers.printer,
            iot_http: this.iotHttp,
        });
    },
    /**
     * Ping all of the IoT Boxes of the devices set on POS config and update the
     * status icon
     */
    pingBoxes() {
        this.setConnectionInfo({ status: "connecting" });
        for (const { ip } of this.iotBoxes) {
            const timeoutController = new AbortController();
            setTimeout(() => timeoutController.abort(), 1000);
            browser
                .fetch(formatEndpoint(ip, "/hw_proxy/hello", odoo.use_lna), {
                    signal: timeoutController.signal,
                    targetAddressSpace: odoo.use_lna ? "local" : undefined,
                })
                .catch(() => ({}))
                .then((response) => this.setProxyConnectionStatus(ip, response.ok || false));
        }
    },
    /**
     * Set the status of the IoT Box that has the specified url.
     *
     * @param {String} ip
     * @param {Boolean} connected
     */
    setProxyConnectionStatus(ip, connected) {
        const iotBox = this.iotBoxes.find((box) => box.ip === ip);
        if (!iotBox) {
            return;
        }
        iotBox.connected = connected;
        const disconnectedBoxes = this.iotBoxes.filter((box) => !box.connected);
        if (disconnectedBoxes.length) {
            this.setConnectionInfo({
                status: "disconnected",
                message: `${disconnectedBoxes.map((box) => box.name).join(" & ")} disconnected`,
            });
        } else {
            this.setConnectionInfo({ status: "connected" });
        }
    },
});
