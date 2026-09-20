import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { DeviceController } from "@iot_base/device_controller";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";

patch(PaymentPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.hardwareProxy = useService("hardware_proxy");
        this.iotLongpolling = useService("iot_longpolling");

        const devices = this.selfOrder.models["iot.device"].getAll();
        const paymentTerminals = devices.filter((device) => device.type === "payment");
        const iotPaymentMethods = this.selfOrder.models["pos.payment.method"]
            .getAll()
            .filter((method) => method.iot_device_id);
        for (const paymentTerminal of paymentTerminals) {
            const deviceProxy = new DeviceController(this.iotLongpolling, paymentTerminal);
            for (const paymentMethod of iotPaymentMethods) {
                if (paymentMethod.iot_device_id.id === paymentTerminal.id) {
                    paymentMethod.terminal_proxy = deviceProxy;
                }
            }
        }
    },

    getPaymentData(order, paymentMethod) {
        const data = {
            messageType: "Transaction",
            TransactionID: parseInt(order.uuid.replace(/-/g, "").slice(0, 16), 16),
            cid: order.uuid,
            amount: Math.round(order.amount_total * 100),
        };
        if (paymentMethod.use_payment_terminal === "worldline") {
            return {
                ...data,
                actionIdentifier: Math.floor(Math.random() * Math.pow(2, 32)),
            };
        }
        if (paymentMethod.use_payment_terminal === "six_iot") {
            return {
                ...data,
                transactionType: "Payment",
                currency: this.selfOrder.currency.name,
                posId: this.selfOrder.session.name,
                userId: this.selfOrder.session.raw.user_id,
            };
        }
        return data;
    },

    async onTerminalMessageReceived(data, order, paymentMethod) {
        if (data.Error) {
            await rpc("/pos-self-order/iot-payment-cancelled", {
                access_token: this.selfOrder.config.access_token,
                order_id: order.id,
            });
            this.selfOrder.handleErrorNotification(data.Error);
            this.selfOrder.paymentError = true;
            paymentMethod.terminal_proxy.removeListener();
        } else if (data.Response === "Approved") {
            await rpc("/pos-self-order/iot-payment-success", {
                access_token: this.selfOrder.config.access_token,
                order_id: order.id,
                payment_method_id: paymentMethod.id,
                payment_info: data,
            });
            paymentMethod.terminal_proxy.removeListener();
        }
    },

    async startPayment() {
        this.selfOrder.paymentError = false;
        const paymentMethod = this.selfOrder.models["pos.payment.method"].find(
            (p) => p.id === this.state.paymentMethodId
        );

        if (!paymentMethod.iot_device_id) {
            return await super.startPayment(...arguments);
        }

        try {
            const orderResult = await rpc(`/kiosk/payment/${this.selfOrder.config.id}/kiosk`, {
                order: this.selfOrder.currentOrder.serializeForORM(),
                access_token: this.selfOrder.access_token,
                payment_method_id: paymentMethod.id,
            });
            const order = orderResult.order[0];

            paymentMethod.terminal_proxy.addListener((data) =>
                this.onTerminalMessageReceived(data, order, paymentMethod)
            );
            await paymentMethod.terminal_proxy.action(this.getPaymentData(order, paymentMethod));
        } catch (error) {
            this.selfOrder.handleErrorNotification(error);
            this.selfOrder.paymentError = true;
        }
    },
});
