import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(SelfOrder.prototype, {
    async setup(...args) {
        await super.setup(...args);
        this.data.connectWebSocket("BLACKBOX_CONFIRMATION", (data) => {
            // handle response
            if (this.currentOrder.id == data.order_id && data.blackbox_response) {
                this.currentOrder.setDataForPushOrderFromBlackbox(data.blackbox_response);
                this.currentOrder.uiState.receipt_type = "NS";
                this.currentOrder.uiState.receiptReady = true;
            }
        });
        this.data.connectWebSocket("BLACKBOX_CLOCK", async (data) => {
            if (this.config.self_ordering_mode === "kiosk") {
                // print clock ticket order
                const orderData = await rpc(`/pos_self_blackbox/get_clock_order/`, {
                    access_token: this.access_token,
                    config_id: this.config.id,
                    order_access_token: data.orderAccessToken,
                    order_id: data.orderId,
                });
                this.models.connectNewData(orderData);
                const order = this.models["pos.order"].find(
                    (o) => o.access_token === data.orderAccessToken
                );
                order.setDataForPushOrderFromBlackbox(data.blackbox_response);
                order.uiState.receipt_type = "NS";
                await this.printer.print(
                    OrderReceipt,
                    {
                        order: order,
                    },
                    { blackboxPrint: true }
                );
                this.models["pos.order"].delete(order);
            }
        });

        if (this.config.self_ordering_mode === "kiosk") {
            // do the clock in if it is not already done
            await this.clock(true);
        }
    },

    async clock(clockIn = true) {
        await rpc(`/pos_self_blackbox/clock/`, {
            access_token: this.access_token,
            config_id: this.config.id,
            clock_in: clockIn,
        });
    },

    initData() {
        super.initData(...arguments);
        if (
            this.config.iface_fiscal_data_module &&
            this.config._product_product_work_in &&
            this.config._product_product_work_out
        ) {
            this.config.work_in_product = this.models["product.product"].get(
                this.config._product_product_work_in
            );
            this.config.work_out_product = this.models["product.product"].get(
                this.config._product_product_work_out
            );
            const fiscal_data_category = this.config.work_in_product.pos_categ_ids[0];
            this.productCategories = this.productCategories.filter(
                (category) => category.id !== fiscal_data_category.id
            );
        }
    },
});
