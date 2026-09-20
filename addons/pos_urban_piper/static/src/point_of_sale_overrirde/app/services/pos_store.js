import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /**
     * @override
     */
    async setup() {
        await super.setup(...arguments);
        this.delivery_order_count = {};
        this.enabledProviders = {};

        // Init provider states from other sources
        if (this.config.module_pos_urban_piper) {
            await this.initProviderStatus();
        }

        this.data.connectWebSocket("URBAN_PIPER_PROVIDER_STATES", async (data) => {
            this.enabledProviders = data;
        });
        if (this.config.module_pos_urban_piper && this.config.urbanpiper_store_identifier) {
            await this._fetchUrbanpiperOrderCount(false);
        }
        this.isSoundPlaying = false;
        this.data.connectWebSocket(
            "PRODUCT_UP_STATUS_CHANGED",
            this.notifyFoodDeliveryStatus.bind(this)
        );
    },

    notifyFoodDeliveryStatus(data) {
        const { product_ids, status } = data;
        const products = this.models["product.template"].filter((product) =>
            product_ids.includes(product.id)
        );
        if (!products.length) {
            return;
        }
        products.forEach((product) => {
            product.setFoodDeliveryAvailability(status, this.config.id);
            this.notification.add(
                _t(
                    "%s is %s online food delivery for all platform in this locations.",
                    product.name,
                    status ? _t("enabled") : _t("disabled")
                ),
                {
                    type: status ? "success" : "warning",
                    sticky: false,
                }
            );
        });
    },

    async saveProviderState(newStates = {}) {
        this.enabledProviders = await this.data.call(
            "pos.config",
            "set_urban_piper_provider_states",
            [this.config.id, JSON.stringify(newStates)]
        );
    },

    async getProviderState() {
        const provideState = await this.data.call("pos.config", "get_urban_piper_provider_states", [
            this.config.id,
        ]);
        return provideState || {};
    },

    async initProviderStatus() {
        // If certain providers are not yet in the status cache, we create it and set it to true.
        let changed = false;
        this.enabledProviders = await this.getProviderState();

        for (const provider of this.config.urbanpiper_delivery_provider_ids) {
            const name = provider.technical_name;
            const currentValue = this.enabledProviders[name];
            const newValue = currentValue === undefined ? true : this.enabledProviders[name];
            if (currentValue === undefined) {
                changed = true; // Initialize provider state to true
            }
            this.enabledProviders[name] = newValue;
        }

        if (changed) {
            await this.saveProviderState(this.enabledProviders);
        }
    },

    async updateStoreStatus(status = false, providerName = false) {
        if (this.config.module_pos_urban_piper && this.config.urbanpiper_store_identifier) {
            await this.data.call("pos.config", "update_store_status", [this.config.id, status], {
                context: {
                    providerName: providerName,
                },
            });
        }
    },

    async getServerOrders() {
        if (this.config.module_pos_urban_piper && this.config.urbanpiper_store_identifier) {
            await this.data.loadServerOrders([
                ["company_id", "=", this.config.company_id.id],
                ["state", "=", "draft"],
                ["session_id", "=", this.session.id],
                [
                    "delivery_provider_id",
                    "in",
                    this.config.urbanpiper_delivery_provider_ids.map((provider) => provider.id),
                ],
            ]);
        }
        return await super.getServerOrders(...arguments);
    },
    _fetchStoreAction(data) {
        const params = {
            type: "success",
            sticky: false,
        };
        let message = "";
        if (data.status) {
            this.enabledProviders[data.platform] = data.action === "enable";
            this.saveProviderState(this.enabledProviders);
        }
        // Prepare notification message
        if (!data.status) {
            params.type = "danger";
            message = _t("Error occurred while updating " + data.platform + " status.");
        } else if (data.action === "enable") {
            message = _t(this.config.name + " is online on " + data.platform + ".");
        } else if (data.action === "disable") {
            message = _t(this.config.name + " is offline on " + data.platform + ".");
        }

        if (message) {
            this.notification.add(message, params);
        }
    },
    get notificationOptions() {
        return {
            type: "success",
            sticky: true,
            buttons: [
                {
                    name: _t("Review Orders"),
                    onClick: () => {
                        this.closeNotificationFn?.();
                        const stateOverride = {
                            search: {
                                fieldName: "DELIVERYPROVIDER",
                                searchTerm:
                                    this.deliveryOrderNotification?.delivery_provider_id.name,
                            },
                            filter: "ACTIVE_ORDERS",
                        };
                        this.setOrder(this.deliveryOrderNotification);
                        if (this.router.state.current == "TicketScreen") {
                            const next = this.defaultPage;
                            this.navigate(next.page, next.params);
                            setTimeout(() => {
                                this.navigate("TicketScreen", { stateOverride });
                                this.env.services.ui.unblock();
                            }, 300);
                            return;
                        }
                        return this.navigate("TicketScreen", { stateOverride });
                    },
                },
            ],
            onClose: () => {
                if (this.isSoundPlaying) {
                    this.sound.stop("order-receive-tone");
                    this.isSoundPlaying = false;
                }
            },
        };
    },

    async _fetchUrbanpiperOrderCount(order_id) {
        try {
            await this.getServerOrders();
        } catch {
            this.notification.add(_t("Order does not load from server"), {
                type: "warning",
                sticky: false,
            });
        }
        const response = await this.data.call(
            "pos.config",
            "get_delivery_data",
            [this.config.id],
            {}
        );
        this.delivery_order_count = response.delivery_order_count;
        this.delivery_providers = response.delivery_providers;
        this.total_new_order = response.total_new_order;
        const deliveryOrder = order_id ? this.models["pos.order"].get(order_id) : false;
        if (!deliveryOrder) {
            return;
        }
        if (deliveryOrder.delivery_status === "acknowledged" && deliveryOrder.state != "cancel") {
            if (!deliveryOrder.isFutureOrder()) {
                await this.sendOrderInPreparationUpdateLastChange(deliveryOrder);
            }
        } else if (deliveryOrder.delivery_status === "placed") {
            if (!this.isSoundPlaying) {
                this.isSoundPlaying = true;
                this.sound.play("order-receive-tone", { loop: true, volume: 1 });
                this.deliveryOrderNotification = deliveryOrder;
                this.closeNotificationFn = this.notification.add(
                    _t("New online order received."),
                    this.notificationOptions
                );
            }
        }
    },

    async goToBack() {
        this.addPendingOrder([this.getOrder().id]);
        await this.syncAllOrders();
        this.navigate("TicketScreen");
        if (this.getOrder().delivery_status !== "placed") {
            try {
                await this.checkPreparationStateAndSentOrderInPreparation(this.getOrder());
            } catch {
                this.notification.add(_t("Error to send in preparation display."), {
                    type: "warning",
                    sticky: false,
                });
            }
        }
    },

    getOrderData(order, reprint) {
        let orderData = super.getOrderData(order, reprint);
        if (order.delivery_provider_id) {
            orderData = {
                ...orderData,
                delivery_provider_id: {
                    id: order.delivery_provider_id.id,
                    name: order.delivery_provider_id.name,
                },
                order_otp: JSON.parse(order.delivery_json)?.order?.details?.ext_platforms?.[0].id,
                prep_time: order.prep_time,
            };
        }
        return orderData;
    },
    async onDeleteOrder(order) {
        if (!order?.delivery_identifier) {
            return super.onDeleteOrder(...arguments);
        }
        this.dialog.add(AlertDialog, {
            title: _t("Online Order"),
            body: _t(
                "Online orders cannot be deleted. If needed, reject the order instead or contact the food delivery provider."
            ),
        });
        return false;
    },
});
