import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { orderInfoPopup } from "@pos_urban_piper/point_of_sale_overrirde/app/components/popups/order_info_popup/order_info_popup";

patch(TicketScreen, {
    props: {
        ...TicketScreen.props,
        upState: { optional: true },
    },
    defaultProps: {
        ...TicketScreen.defaultProps,
        upState: "",
    },
});

patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.order_status = {
            placed: "Placed",
            acknowledged: "Acknowledged",
            food_ready: "Food Ready",
            dispatched: "Dispatched",
            completed: "Completed",
            cancelled: "Cancelled",
        };
        this.state.upState = this.props.upState;
    },

    /**
     * @override
     * Add two search fields.
     */
    _getSearchFields() {
        return Object.assign({}, super._getSearchFields(...arguments), {
            DELIVERYPROVIDER: {
                repr: (order) => order.getDeliveryProviderName(),
                displayName: _t("Delivery Channel"),
                modelField: "delivery_provider_id.name",
            },
            ORDERSTATUS: {
                repr: (order) => order.getOrderStatus(),
                displayName: _t("Delivery Order Status"),
                modelField: "delivery_status",
            },
        });
    },

    async _handleResponse(response, order, new_status) {
        const { is_success, message } = response;
        if (!is_success) {
            this.pos.notification.add(message, { type: "warning", sticky: false });
            return false;
        }
        order.delivery_status = new_status;
        return true;
    },

    async _updateScreenState(order, filterState, upState = "") {
        this.state.upState = upState;
        await this.onSearch({
            fieldName: "DELIVERYPROVIDER",
            searchTerm: order?.delivery_provider_id?.name,
        });
        await this.onFilterSelected(filterState);
    },

    async _updateOrderStatus(order, status, code = null) {
        const urban_piper_test = JSON.parse(order.delivery_json)?.order?.urban_piper_test;
        const response = await this.pos.data.call("pos.config", "order_status_update", [
            this.pos.config.id,
            order.id,
            status,
            code,
            urban_piper_test,
            {
                orderPrepTime: order.prep_time,
            },
        ]);
        return response;
    },

    async _acceptOrder(order) {
        const syncedOrder = this.pos.models["pos.order"].get(order.id);
        const response = await this._updateOrderStatus(syncedOrder, "Acknowledged");
        const status = await this._handleResponse(response, syncedOrder, "acknowledged");
        if (status) {
            this._updateScreenState(syncedOrder, "ACTIVE_ORDERS");
            syncedOrder.uiState.orderAcceptTime = luxon.DateTime.now().ts;
        }
    },

    async _rejectOrder(order) {
        if (
            ["deliveroo", "", "hungerstation"].includes(order.delivery_provider_id.technical_name)
        ) {
            return this.dialog.add(AlertDialog, {
                title: _t("Error"),
                body: _t(`Rejecting this order is not allowed for "%(providerName)s"`, {
                    providerName: order.delivery_provider_id.name,
                }),
            });
        }
        this.dialog.add(SelectionPopup, {
            title: _t("Reject Order"),
            list: [
                { id: 1, item: "item_out_of_stock", label: _t("Product is out of Stock") },
                { id: 2, item: "store_closed", label: _t("Store is Closed") },
                { id: 3, item: "store_busy", label: _t("Store is Busy") },
                { id: 4, item: "rider_not_available", label: _t("Rider is Not Available") },
                { id: 5, item: "invalid_item", label: _t("Invalid Product") },
                { id: 6, item: "out_of_delivery_radius", label: _t("Out of Delivery Radius") },
                { id: 7, item: "connectivity_issue", label: _t("Connectivity Issue") },
                { id: 8, item: "total_missmatch", label: _t("Total Missmatch") },
                { id: 9, item: "option_out_of_stock", label: _t("Variants/Addons out of Stock") },
                { id: 10, item: "invalid_option", label: _t("Invalid Variant/Addons") },
                { id: 11, item: "unspecified", label: _t("Others") },
            ],
            getPayload: async (code) => {
                const last_order_status = order.delivery_status;
                order.state = "cancel";
                const response = await this._updateOrderStatus(order, "Cancelled", code);
                const status = await this._handleResponse(response, order, "cancelled");
                if (status) {
                    if (
                        Object.keys(order.last_order_preparation_change.lines).length == 0 &&
                        last_order_status !== "placed"
                    ) {
                        if (order.general_customer_note) {
                            order.last_order_preparation_change.general_customer_note =
                                order.general_customer_note;
                        }
                        await this.pos.checkPreparationStateAndSentOrderInPreparation(order, {
                            cancelled: true,
                        });
                    }
                    await this._updateScreenState(order, "ACTIVE_ORDERS");
                    await this.pos.deleteOrders([order]);
                    await this.pos.afterOrderDeletion();
                    this.setSelectedOrder(this.pos.getOrder());
                }
            },
        });
    },

    async _doneOrder(order) {
        const response = await this._updateOrderStatus(order, "Food Ready");
        const status = await this._handleResponse(response, order, "food_ready");
        if (status) {
            this._updateScreenState(order, "SYNCED", "DONE");
        }
        await this.pos.data.loadServerOrders([["uuid", "=", order.uuid]]);

        // make sure the order is identified as paid.
        order = this.pos.models["pos.order"].get(order.id);
        this.state.selectedOrderUuid = order.uuid;
        order.setScreenData({ name: "" });
        await super._doneOrder(...arguments);
    },

    async _dispatchOrder(order) {
        const response = await this._updateOrderStatus(order, "Dispatched");
        await this._handleResponse(response, order, "dispatched");
    },

    async _completeOrder(order) {
        const response = await this._updateOrderStatus(order, "Completed");
        await this._handleResponse(response, order, "completed");
    },

    async _onInfoOrder(order) {
        this.dialog.add(orderInfoPopup, {
            order: order,
            order_status: this.order_status,
        });
    },

    /**
     * @override
     * Return results based on upState.
     */
    getFilteredOrderList() {
        const orders = super.getFilteredOrderList();
        if (!this.state.upState) {
            return orders;
        }

        const statusMapping = {
            NEW: "placed",
            ONGOING: "acknowledged",
            DONE: ["food_ready", "dispatched", "completed"],
        };

        const filteredOrders = orders.filter((order) => {
            if (this.state.upState === "DONE") {
                return statusMapping.DONE.includes(order.delivery_status);
            }
            return order.delivery_status === statusMapping[this.state.upState];
        });

        return filteredOrders;
    },

    fetchOrderOtp() {
        return JSON.parse(this.order.delivery_json)?.order?.details?.ext_platforms?.[0].id;
    },

    /**
     * @override
     */
    getDate(order) {
        if (order?.delivery_identifier) {
            if (
                order.date_order.toLocal().startOf("day").ts ===
                luxon.DateTime.now().startOf("day").ts
            ) {
                return _t("Today");
            }
            return order.date_order.toFormat("MM/dd/yyyy");
        }
        return super.getDate(order);
    },

    /**
     * @override
     */
    async onFilterSelected(selectedFilter) {
        if (this.state.upState && this.state.filter != selectedFilter) {
            this.state.upState = "";
        }
        super.onFilterSelected(selectedFilter);
    },

    /**
     * @override
     */
    async onSearch(search) {
        if (this.state.upState && this.state.search != search) {
            this.state.upState = "";
        }
        super.onSearch(search);
    },

    /**
     * @override
     */
    postRefund(destinationOrder) {
        destinationOrder.isDeliveryRefundOrder = this.getSelectedOrder()?.delivery_identifier
            ? true
            : false;
        return super.postRefund(destinationOrder);
    },
});
