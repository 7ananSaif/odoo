import { IoTPrinter } from "@pos_iot/app/utils/printer/iot_printer";
import { DeviceController } from "@iot_base/device_controller";
import { SelfOrder, selfOrderService } from "@pos_self_order/app/services/self_order_service";
import { patch } from "@web/core/utils/patch";

patch(selfOrderService, {
    dependencies: [...selfOrderService.dependencies, "iot_longpolling", "iot_http"],
});

patch(SelfOrder.prototype, {
    async setup(env, services) {
        this.iot_longpolling = services.iot_longpolling;
        this.iotHttpService = services.iot_http;
        await super.setup(...arguments);

        this.iotHttpService.cacheIotBoxRecords(this.models["iot.box"].getAll());

        if (!this.config.iface_print_via_proxy || this.config.self_ordering_mode !== "kiosk") {
            return;
        }

        const device = new DeviceController(this.iot_longpolling, this.config.iface_printer_id);
        this.printer.setPrinter(
            new IoTPrinter({
                device,
                iot_http: this.iotHttpService,
                access_token: this.access_token,
            })
        );
    },

    filterPaymentMethods(paymentMethods) {
        const otherPaymentMethods = super.filterPaymentMethods(...arguments);
        const iotPaymentMethods = paymentMethods.filter(
            (paymentMethod) => paymentMethod.iot_device_id != null
        );
        return [...new Set([...otherPaymentMethods, ...iotPaymentMethods])];
    },

    createPrinter(printer) {
        if (printer.device_identifier && printer.printer_type === "iot") {
            if (!printer.device_id?.id || !printer.device_id?.iot_id) {
                console.error("Error loading data, missing Iot Box or device");
                return false;
            }

            const deviceController = new DeviceController(this.iot_longpolling, printer.device_id);
            return new IoTPrinter({
                device: deviceController,
                iot_http: this.iotHttpService,
                access_token: this.access_token,
            });
        } else {
            return super.createPrinter(...arguments);
        }
    },
});
