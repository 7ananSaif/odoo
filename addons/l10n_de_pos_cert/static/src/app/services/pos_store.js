import { CONSOLE_COLOR, PosStore } from "@point_of_sale/app/services/pos_store";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import { patch } from "@web/core/utils/patch";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";
import { uuidv4 } from "@point_of_sale/utils";

const RATE_ID_MAPPING = {
    1: "NORMAL",
    2: "REDUCED_1",
    3: "SPECIAL_RATE_1",
    4: "SPECIAL_RATE_2",
    5: "NULL",
};

patch(PosStore.prototype, {
    // @Override
    async setup() {
        this.token = "";
        this.vatRateMapping = {};
        this.validateOrderFree = false;
        await super.setup(...arguments);
    },
    // @Override
    async _onBeforeDeleteOrder(order) {
        try {
            if (this.isCountryGermanyAndFiskaly() && order.isTransactionStarted()) {
                await this.cancelTransaction(order);
            }
            return super._onBeforeDeleteOrder(...arguments);
        } catch (error) {
            const message = {
                noInternet: _t(
                    "Check the internet connection then try to validate or cancel the order. " +
                        "Do not delete your browsing, cookies and cache data in the meantime!"
                ),
                unknown: _t(
                    "An unknown error has occurred! Try to validate this order or cancel it again. " +
                        "Please contact Odoo for more information."
                ),
            };
            this.fiskalyError(error, message);
            return false;
        }
    },
    //@Override
    async afterProcessServerData() {
        if (this.isCountryGermanyAndFiskaly()) {
            const data = await this.data.call("pos.config", "l10n_de_get_fiskaly_urls_and_keys", [
                this.config.id,
            ]);

            this.company.l10n_de_fiskaly_api_key = data["api_key"];
            this.company.l10n_de_fiskaly_api_secret = data["api_secret"];
            this.useKassensichvVersion2 = this.config.l10n_de_fiskaly_tss_id.includes("|");
            this.apiUrl =
                data["kassensichv_url"] + "/api/v" + (this.useKassensichvVersion2 ? "2" : "1"); // use correct version
            this.initVatRates(data["dsfinvk_url"] + "/api/v0");
        }
        return super.afterProcessServerData(...arguments);
    },
    _authenticate() {
        const data = {
            api_key: this.company.l10n_de_fiskaly_api_key,
            api_secret: this.company.l10n_de_fiskaly_api_secret,
        };

        return fetch(this.getApiUrl() + "/auth", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        })
            .then((response) => response.json())
            .then((data) => {
                this.setApiToken(data.access_token);
            })
            .catch((error) => {
                error.source = "authenticate";
                return Promise.reject(error);
            });
    },
    async createTransaction(order) {
        const transactionUuid = uuidv4();
        const data = {
            state: "ACTIVE",
            client_id: this.getClientId(),
        };
        const payload = `${transactionUuid}${this.isUsingApiV2() ? "?tx_revision=1" : ""}`;
        await this.transactionCall(payload, data, order);
        // Success
        order.l10n_de_fiskaly_transaction_uuid = transactionUuid;
        order.transactionStarted();
    },
    _createAmountPerVatRateArray(order) {
        const vatRateMap = {
            "VAT 0%": "NULL",
            "VAT 7%": "REDUCED_1",
            "VAT 19%": "NORMAL",
            "VAT 10,7%": "SPECIAL_RATE_1",
            "VAT 5,5%": "SPECIAL_RATE_2",
        };

        const orderSign = order.prices.taxDetails.order_sign;
        const expectedBase = order.prices.taxDetails.base_amount;
        let baseAmountSum = 0;
        const result = order.prices.taxDetails.subtotals[0].tax_groups.map((group) => {
            const amount = parseFloat((group.tax_amount + group.base_amount) * orderSign);
            baseAmountSum += group.base_amount;
            return {
                vat_rate: vatRateMap[group.group_name] || "NULL",
                amount: amount.toFixed(5),
            };
        });

        // Adjustments (e.g., gift cards, tips) may lack tax info, default it to 0% to avoid mismatches.
        const difference = parseFloat(
            (expectedBase + order.requiredSettlementAmount() - baseAmountSum) * orderSign
        );
        if (difference) {
            const existingNullEntry = result.find((item) => item.vat_rate === "NULL");
            if (existingNullEntry) {
                existingNullEntry.amount = this.currency.round(
                    parseFloat(existingNullEntry.amount) + difference
                );
            } else {
                result.push({
                    vat_rate: "NULL",
                    amount: `${this.currency.round(difference)}`,
                });
            }
        }
        return result;
    },
    async finishShortTransaction(order) {
        const amountPerVatRateArray = this._createAmountPerVatRateArray(order);
        const amountPerPaymentTypeArray = order._createAmountPerPaymentTypeArray();
        const data = {
            state: "FINISHED",
            client_id: this.getClientId(),
            schema: {
                standard_v1: {
                    receipt: {
                        receipt_type: "RECEIPT",
                        amounts_per_vat_rate: amountPerVatRateArray,
                        amounts_per_payment_type: amountPerPaymentTypeArray,
                    },
                },
            },
        };
        const payload = `${order.l10n_de_fiskaly_transaction_uuid}?${
            this.isUsingApiV2() ? "tx_revision=2" : "last_revision=1"
        }`;
        const result = await this.transactionCall(payload, data, order);
        // Success
        if (!order.uiState.fiskalyServerError) {
            order._updateTssInfo(result);
        }
    },
    async cancelTransaction(order) {
        const data = {
            state: "CANCELLED",
            client_id: this.getClientId(),
            schema: {
                standard_v1: {
                    receipt: {
                        receipt_type: "CANCELLATION",
                        amounts_per_vat_rate: [],
                    },
                },
            },
        };
        const payload = `${order.l10n_de_fiskaly_transaction_uuid}?${
            this.isUsingApiV2() ? "tx_revision=2" : "last_revision=1"
        }`;
        return await this.transactionCall(payload, data, order);
    },
    async transactionCall(payload, data, order, retryCount = 0) {
        const token = this.getApiToken();
        try {
            if (!token) {
                await this._authenticate();
            }
            const response = await fetch(
                `${this.getApiUrl()}/tss/${this.getTssId()}/tx/${payload}`,
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    method: "PUT",
                    body: JSON.stringify(data),
                }
            );
            const result = await response.json();
            if (!response.ok) {
                const errorCode = await this.handleRequestError(result, order, retryCount);
                if (errorCode === "retry") {
                    return await this.transactionCall(payload, data, order, retryCount + 1);
                }
            }
            return result;
        } catch (error) {
            // Need to reject to keep track of rejected orders in syncAllOrders
            // don't show popup for single order failures, it should be handled later in syncAllOrders
            logPosMessage("Store", "transactionCall", "Error", CONSOLE_COLOR, [error]);
            return Promise.reject(error);
        }
    },
    async handleRequestError(result, order, retryCount) {
        if (result.status_code === 401) {
            if (!retryCount) {
                await this._authenticate();
                return "retry";
            }
        } else if (result.status_code >= 500 && result.status_code <= 599) {
            if (retryCount < 2) {
                const delay = (retryCount + 1) * 1000;
                await new Promise((resolve) => setTimeout(resolve, delay));
                return "retry";
            } else {
                order.uiState.fiskalyServerError = true; // server unreachable after retries
                return;
            }
        }
        // Need for keeping track of rejected orders in syncAllOrders
        return Promise.reject(result);
    },
    getApiToken() {
        return this.token;
    },
    setApiToken(token) {
        this.token = token;
    },
    getApiUrl() {
        return this.apiUrl;
    },
    getApiKey() {
        return this.company.l10n_de_fiskaly_api_key;
    },
    getApiSecret() {
        return this.company.l10n_de_fiskaly_api_secret;
    },
    getTssId() {
        return (
            this.config.l10n_de_fiskaly_tss_id && this.config.l10n_de_fiskaly_tss_id.split("|")[0]
        );
    },
    getClientId() {
        return this.config.l10n_de_fiskaly_client_id;
    },
    isUsingApiV2() {
        return this.useKassensichvVersion2;
    },
    isCountryGermany() {
        return this.config.is_company_country_germany;
    },
    isCountryGermanyAndFiskaly() {
        return this.isCountryGermany() && !!this.getTssId();
    },
    initVatRates(url) {
        const data = {
            api_key: this.getApiKey(),
            api_secret: this.getApiSecret(),
        };

        return fetch(url + "/auth", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Auth request failed");
                }
                return response.json();
            })
            .then((data) =>
                fetch(url + "/vat_definitions", {
                    headers: { Authorization: `Bearer ${data.access_token}` },
                })
            )
            .then((response) => {
                if (!response.ok) {
                    throw new Error("VAT definitions request failed");
                }
                return response.json();
            })
            .then((vat_data) => {
                vat_data.data.forEach((vat_definition) => {
                    if (!(vat_definition.percentage in this.vatRateMapping)) {
                        this.vatRateMapping[vat_definition.percentage] =
                            RATE_ID_MAPPING[vat_definition.vat_definition_export_id];
                    }
                });
            })
            .catch((error) => {
                logPosMessage("Store", "initVatRates", "Error fetching VAT data", CONSOLE_COLOR, [
                    error,
                ]);
                // This is a fallback where we hardcode the taxes hoping that they didn't change ...
                this.vatRateMapping = {
                    19: "NORMAL",
                    7: "REDUCED_1",
                    10.7: "SPECIAL_RATE_1",
                    5.5: "SPECIAL_RATE_2",
                    0: "NULL",
                };
            });
    },
    //@Override
    /**
     * This function first attempts to send the orders remaining in the queue to Fiskaly before trying to
     * send it to Odoo. Two cases can happen:
     * - Failure to send to Fiskaly => we assume that if one order fails, EVERY order will fail
     * - Failure to send to Odoo => the order is already sent to Fiskaly, we store them locally with the TSS info
     */
    async syncAllOrders(options = {}) {
        if (!this.isCountryGermanyAndFiskaly()) {
            return super.syncAllOrders(options);
        }

        const { orderToCreate, orderToUpdate } = this.getPendingOrder();
        const orders = [...orderToCreate, ...orderToUpdate];

        if (orders.length === 0 || this.data.network.offline) {
            orders.forEach((order) => {
                order.uiState.networkError = true;
            });
            return super.syncAllOrders({ ...options, orders });
        }

        const orderObjectMap = {};
        for (const order of orders) {
            orderObjectMap[order.id] = order;
        }

        let fiskalyError;
        const sentToFiskaly = [];
        const fiskalyFailure = [];
        const ordersToUpdate = {};
        for (const order of orders) {
            try {
                const orderObject = orderObjectMap[order.id];
                if (
                    !fiskalyError &&
                    !orderObject.uiState.fiskalyServerError &&
                    !orderObject.uiState.networkError
                ) {
                    if (orderObject.isTransactionInactive()) {
                        await this.createTransaction(orderObject);
                        ordersToUpdate[order.id] = true;
                    }
                    if (orderObject.isTransactionStarted() && !this.config.module_pos_restaurant) {
                        // In restaurant only finish the transaction at validation not every time we order
                        await this.finishShortTransaction(order);
                        ordersToUpdate[order.id] = true;
                    }
                }
                if (
                    !orderObject.isTransactionInactive() ||
                    orderObject.uiState.fiskalyServerError ||
                    orderObject.uiState.networkError
                ) {
                    sentToFiskaly.push(order);
                } else {
                    fiskalyFailure.push(order);
                }
            } catch (error) {
                fiskalyError = error;
                fiskalyError.code = "fiskaly";
                fiskalyFailure.push(order);
            }
        }

        let result, odooError;
        if (sentToFiskaly.length > 0) {
            for (const orderJson of sentToFiskaly) {
                if (ordersToUpdate[orderJson["id"]]) {
                    orderJson["data"] = orderObjectMap[orderJson["id"]].raw;
                }
            }
            try {
                result = await super.syncAllOrders({ ...options, orders });
            } catch (error) {
                odooError = error;
            }
        }
        if (fiskalyFailure.length === 0 && !odooError) {
            return result;
        } else {
            if (Object.keys(ordersToUpdate).length) {
                for (const orderJson of fiskalyFailure) {
                    if (ordersToUpdate[orderJson["id"]]) {
                        orderJson["data"] = orderObjectMap[orderJson["id"]].raw;
                    }
                }
            }
            throw odooError || fiskalyError;
        }
    },
    async fiskalyError(error, message) {
        if (error.status === 0 || this.data.network.offline) {
            const title = _t("No internet");
            const body = message.noInternet;
            this.dialog.add(AlertDialog, { title, body });
        } else if (error.status_code === 401) {
            await this._showUnauthorizedPopup();
        } else if (
            (error.status_code === 400 && error.message?.includes("tss_id")) ||
            (error.status_code === 404 && error.code === "E_TSS_NOT_FOUND")
        ) {
            await this._showBadRequestPopup("TSS ID");
        } else if (
            (error.status_code === 400 && error.message?.includes("client_id")) ||
            (error.status_code === 400 && error.code === "E_CLIENT_NOT_FOUND")
        ) {
            // the api is actually sending an 400 error for a "Not found" error
            await this._showBadRequestPopup("Client ID");
        } else {
            const title = error.error || _t("Unknown error");
            const body = error.message || message.unknown;
            this.dialog.add(AlertDialog, { title, body });
        }
    },
    async showFiskalyNoInternetConfirmPopup(event) {
        const confirmed = await ask(this.dialog, {
            title: _t("Problem with internet"),
            body: _t(
                "You can either wait for the connection issue to be resolved or continue with a non-compliant receipt (the order will still be sent to Fiskaly once the connection issue is resolved).\n" +
                    "Do you want to continue with a non-compliant receipt?"
            ),
        });
        if (confirmed) {
            event.detail();
        }
    },
    async _showBadRequestPopup(data) {
        const title = _t("Bad request");
        const body = _t("Your %s is incorrect. Update it in your PoS settings", data);
        this.dialog.add(AlertDialog, { title, body });
    },
    async _showUnauthorizedPopup() {
        const title = _t("Unauthorized error to Fiskaly");
        const body = _t(
            "It seems that your Fiskaly API key and/or secret are incorrect. Update them in your company settings."
        );
        this.dialog.add(AlertDialog, { title, body });
    },
    async _processSaleOrder(sale_order) {
        if (
            sale_order.partner_id &&
            this.isCountryGermanyAndFiskaly() &&
            (!sale_order.partner_id.street || !sale_order.partner_id.zip)
        ) {
            return this.dialog.add(ConfirmationDialog, {
                title: _t("Invalid or missing customer information"),
                body: _t(
                    "The customer of the selected sale order must have a street and ZIP code.\nUpdate the customer's details to continue."
                ),
            });
        }
        return super._processSaleOrder(sale_order);
    },
});
