import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { convertFromEpoch } from "@l10n_de_pos_cert/app/utils/utils";
import { patch } from "@web/core/utils/patch";
import { roundCurrency } from "@point_of_sale/app/models/utils/currency";

patch(PosOrder.prototype, {
    // @Override
    setup(vals) {
        super.setup(...arguments);
        if (this.isCountryGermanyAndFiskaly()) {
            this.fiskalyUuid = this.fiskalyUuid || "";
            // Init the tssInformation with the values from the config
            this.l10n_de_fiskaly_transaction_uuid = vals.l10n_de_fiskaly_transaction_uuid || false;
            this.l10n_de_fiskaly_transaction_number =
                vals.l10n_de_fiskaly_transaction_number || false;
            this.l10n_de_fiskaly_time_start = vals.l10n_de_fiskaly_time_start || false;
            this.l10n_de_fiskaly_time_end = vals.l10n_de_fiskaly_time_end || false;
            this.l10n_de_fiskaly_certificate_serial =
                vals.l10n_de_fiskaly_certificate_serial || false;
            this.l10n_de_fiskaly_timestamp_format = vals.l10n_de_fiskaly_timestamp_format || false;
            this.l10n_de_fiskaly_signature_value = vals.l10n_de_fiskaly_signature_value || false;
            this.l10n_de_fiskaly_signature_algorithm =
                vals.l10n_de_fiskaly_signature_algorithm || false;
            this.l10n_de_fiskaly_signature_public_key =
                vals.l10n_de_fiskaly_signature_public_key || false;
            this.l10n_de_fiskaly_client_serial_number =
                vals.l10n_de_fiskaly_client_serial_number || false;
        }
    },
    initState() {
        super.initState();
        this.uiState = {
            ...this.uiState,
            transactionState: this.uiState.transactionState || "inactive", // Used to know when we need to create the fiskaly transaction,
            fiskalyServerError: this.uiState.fiskalyServerError || false,
            networkError: this.uiState.networkError || false,
        };
    },
    get tss() {
        if (this.isCountryGermanyAndFiskaly()) {
            if (this.isTransactionFinished()) {
                return {
                    transaction_number: {
                        name: "TSE-Transaktion",
                        value: this.l10n_de_fiskaly_transaction_number,
                    },
                    time_start: { name: "TSE-Start", value: this.l10n_de_fiskaly_time_start },
                    time_end: { name: "TSE-Stop", value: this.l10n_de_fiskaly_time_end },
                    certificate_serial: {
                        name: "TSE-Seriennummer",
                        value: this.l10n_de_fiskaly_certificate_serial,
                    },
                    timestamp_format: {
                        name: "TSE-Zeitformat",
                        value: this.l10n_de_fiskaly_timestamp_format,
                    },
                    signature_value: {
                        name: "TSE-Signatur",
                        value: this.l10n_de_fiskaly_signature_value,
                    },
                    signature_algorithm: {
                        name: "TSE-Hashalgorithmus",
                        value: this.l10n_de_fiskaly_signature_algorithm,
                    },
                    signature_public_key: {
                        name: "TSE-PublicKey",
                        value: this.l10n_de_fiskaly_signature_public_key,
                    },
                    client_serial_number: {
                        name: "ClientID / KassenID",
                        value: this.l10n_de_fiskaly_client_serial_number,
                    },
                    erstBestellung: {
                        name: "TSE-Erstbestellung",
                        value: this.getOrderlines()[0].getProduct().display_name,
                    },
                };
            } else {
                // When there is TSS server is unreachable
                return {
                    tss_issue: true,
                };
            }
        } else if (this.isCountryGermany() && !this.getTssId()) {
            return {
                test_environment: true,
            };
        }

        return false;
    },
    isCountryGermanyAndFiskaly() {
        return this.isCountryGermany() && !!this.getTssId();
    },
    getTssId() {
        return (
            this.config.l10n_de_fiskaly_tss_id && this.config.l10n_de_fiskaly_tss_id.split("|")[0]
        );
    },
    isCountryGermany() {
        return this.config.is_company_country_germany;
    },
    isTransactionInactive() {
        return this.uiState.transactionState === "inactive";
    },
    transactionStarted() {
        this.uiState.transactionState = "started";
    },
    isTransactionStarted() {
        return this.uiState.transactionState === "started";
    },
    transactionFinished() {
        this.uiState.transactionState = "finished";
    },
    isTransactionFinished() {
        return this.uiState.transactionState === "finished" || this.l10n_de_fiskaly_time_start;
    },
    /*
     *  Return an array of { 'payment_type': ..., 'amount': ...}
     */
    _createAmountPerPaymentTypeArray() {
        const amountPerPaymentTypeArray = [];
        this.payment_ids.forEach((line) => {
            const type = line.payment_method_id.type === "cash" ? "CASH" : "NON_CASH";
            const amount = roundCurrency(line.amount, this.currency);
            const existing = amountPerPaymentTypeArray.find((entry) => entry.payment_type === type);

            if (existing) {
                existing.amount = roundCurrency(
                    parseFloat(existing.amount) + amount,
                    this.currency
                ).toFixed(2);
            } else {
                amountPerPaymentTypeArray.push({
                    payment_type: type,
                    amount: this.currency.round(amount).toFixed(2),
                });
            }
        });
        if (this.change) {
            amountPerPaymentTypeArray.push({
                payment_type: "CASH",
                amount: roundCurrency(-this.change, this.currency).toFixed(2),
            });
        }

        // Reduce receivable payment which will be shown as paid when paid using deposit/settlement
        const nonCashPaymentType = amountPerPaymentTypeArray.find(
            (l) => l.payment_type === "NON_CASH"
        );
        const adjustment = this.requiredSettlementAmount();
        if (nonCashPaymentType && adjustment) {
            if (!nonCashPaymentType) {
                amountPerPaymentTypeArray.push({
                    payment_type: "NON_CASH",
                    amount: "0.00",
                });
            }
            nonCashPaymentType.amount = roundCurrency(
                parseFloat(nonCashPaymentType.amount) + adjustment,
                this.currency
            ).toFixed(2);
        }

        return amountPerPaymentTypeArray;
    },
    requiredSettlementAmount() {
        // Overall payment through receivable pm needs to be adjusted
        const totalReceivablePayment = this.payment_ids
            .filter((line) => !line.payment_method_id.journal_id)
            .reduce((sum, line) => sum + line.amount, 0);
        return -totalReceivablePayment;
    },
    _updateTimeStart(seconds) {
        this.l10n_de_fiskaly_time_start = convertFromEpoch(seconds);
    },
    _updateTssInfo(data) {
        this.l10n_de_fiskaly_transaction_number = data.number;
        this._updateTimeStart(data.time_start);
        this.l10n_de_fiskaly_time_end = convertFromEpoch(data.time_end);
        // certificate_serial is now called tss_serial_number in the v2 api
        this.l10n_de_fiskaly_certificate_serial = data.tss_serial_number
            ? data.tss_serial_number
            : data.certificate_serial;
        this.l10n_de_fiskaly_timestamp_format = data.log.timestamp_format;
        this.l10n_de_fiskaly_signature_value = data.signature.value;
        this.l10n_de_fiskaly_signature_algorithm = data.signature.algorithm;
        this.l10n_de_fiskaly_signature_public_key = data.signature.public_key;
        this.l10n_de_fiskaly_client_serial_number = data.client_serial_number;
        this.transactionFinished();
    },
});
