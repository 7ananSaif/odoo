import { patch } from "@web/core/utils/patch";
import { PosStore, posService } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { DeviceController } from "@iot_base/device_controller";
import { IoTPrinter } from "@pos_iot/app/utils/printer/iot_printer";

patch(posService, {
    dependencies: [...posService.dependencies, "iot_http"],
});

patch(PosStore.prototype, {
    async setup(env, { iot_http }) {
        this.iotHttp = iot_http;
        await super.setup(...arguments);
        this.env.services.iot_longpolling.setLna(odoo.use_lna);
    },
    async processServerData(loadedData) {
        await super.processServerData(...arguments);

        this._loadIotDevice(this.models["iot.device"].getAll());
        this.hardwareProxy.iotBoxes = this.models["iot.box"].getAll();
        this.iotHttp.cacheIotBoxRecords(this.hardwareProxy.iotBoxes);
    },
    _loadIotDevice(devices) {
        const iotLongpolling = this.env.services.iot_longpolling;
        for (const device of devices) {
            const { deviceControllers } = this.hardwareProxy;
            const { type, identifier } = device;
            const deviceProxy = new DeviceController(iotLongpolling, device);
            if (type === "payment") {
                for (const pm of this.models["pos.payment.method"].getAll()) {
                    if (pm.iot_device_id?.id === device.id) {
                        pm.terminal_proxy = deviceProxy;
                    }
                }
            } else if (type === "scanner") {
                deviceControllers.scanners ||= {};
                deviceControllers.scanners[identifier] = deviceProxy;
            } else if (type === "printer") {
                if (this.config.iface_printer_id?.id === device.id) {
                    deviceControllers.printer = deviceProxy;
                }
            } else {
                deviceControllers[type] = deviceProxy;
            }
        }
    },
    createPrinter(config) {
        if (config.device_identifier && config.printer_type === "iot") {
            const device = this.models["iot.device"].get(config.device_id) ?? {
                iot_ip: config.proxy_ip,
                identifier: config.device_identifier,
            };
            const deviceController = new DeviceController(
                this.env.services.iot_longpolling,
                device
            );
            return new IoTPrinter({ device: deviceController, iot_http: this.iotHttp });
        } else {
            return super.createPrinter(...arguments);
        }
    },

    showScreen(name, props, newOrder = false) {
        if (
            this.router.state.current === "PaymentScreen" &&
            this.getOrder()?.payment_ids.some(
                (pl) =>
                    pl.payment_method_id.use_payment_terminal === "worldline" &&
                    ["waiting", "waitingCard", "waitingCancel"].includes(pl.payment_status)
            )
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Transaction in progress"),
                body: _t("Please process or cancel the current transaction."),
            });
        } else {
            return super.showScreen(...arguments);
        }
    },
    connectToProxy() {
        this.hardwareProxy.pingBoxes();
        if (this.config.iface_scan_via_proxy) {
            this.barcodeReader?.connectToProxy();
        }
        if (!this.hardwareProxy.printer && this.config.iface_print_via_proxy) {
            this.hardwareProxy.connectToPrinter();
        }
        return Promise.resolve();
    },
});
