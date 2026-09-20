import { floatCompare } from "@point_of_sale/utils";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatFloat, roundPrecision } from "@web/core/utils/numbers";
import { Reactive } from "@web/core/utils/reactive";

// This is functionally identical to the base ScaleService with `pos_iot` patch applied.
// Having a separate copy allows us to keep a certified version that will only change
// if absolutely necessary, whilst the base service is free to change.

const TARE_TIMEOUT_MS = 3000;

export class CertifiedScaleService extends Reactive {
    constructor(env, deps) {
        super(...arguments);
        this.setup(env, deps);
    }

    setup(env, deps) {
        this.env = env;
        this.hardwareProxy = deps.hardware_proxy;
        this.lastWeight = null;
        this.weight = 0;
        this.reset();
    }

    start(errorCallback) {
        this.onError = errorCallback;
        if (!this.isManualMeasurement) {
            this.isMeasuring = true;
            this._readWeightContinuously();
        }
    }

    reset() {
        if (this.isMeasuring) {
            this._scaleDevice?.removeListener();
            this._scaleDevice?.action({ action: "stop_reading" });
        }
        this.tare = 0;
        this.tareRequested = false;
        this.loading = false;
        this.isMeasuring = false;
        this.product = null;
        this.onError = null;
    }

    confirmWeight() {
        this.lastWeight = this.weight;
        return this.netWeight;
    }

    async readWeight() {
        this.loading = true;
        try {
            this._checkScaleIsConnected();
            this.weight = await this._getWeightFromScale();
            this._clearLastWeightIfValid();
        } catch (error) {
            this.isMeasuring = false;
            this.onError?.(error.message);
        }
        this.loading = false;
        this._setTareIfRequested();
    }

    _checkScaleIsConnected() {
        if (this.hardwareProxy.connectionInfo.status !== "connected") {
            throw new Error(_t("Cannot weigh product - IoT Box is disconnected"));
        }
        if (this.hardwareProxy.connectionInfo.drivers.scale?.status !== "connected") {
            throw new Error(_t("Cannot weigh product - Scale is not connected to IoT Box"));
        }
    }

    async _getWeightFromScale() {
        const weightPromise = new Promise((resolve, reject) => {
            this._scaleDevice.addListener((data) => {
                try {
                    resolve(this._handleScaleMessage(data));
                } catch (error) {
                    reject(error);
                }
                this._scaleDevice.removeListener();
            });
        });
        await this._scaleDevice.action({ action: "read_once" });
        return weightPromise;
    }

    _readWeightContinuously() {
        try {
            this._checkScaleIsConnected();
        } catch (error) {
            this.onError?.(error.message);
            this.isMeasuring = false;
            return;
        }

        this._scaleDevice.addListener((data) => {
            try {
                this.weight = this._handleScaleMessage(data);
                this._clearLastWeightIfValid();
                this._setTareIfRequested();
            } catch (error) {
                this.onError?.(error.message);
            }
        });
        // The IoT box only sends the weight when it changes, so we
        // manually read to get the initial value.
        this._scaleDevice.action({ action: "read_once" });
        this._scaleDevice.action({ action: "start_reading" });
    }

    _handleScaleMessage(data) {
        if (data.status.status === "error") {
            throw new Error(`Cannot weigh product - ${data.status.message_body}`);
        } else {
            return data.value || 0;
        }
    }

    setProduct(product, decimalAccuracy, unitPrice) {
        this.product = {
            name: product.display_name || _t("Unnamed Product"),
            unitOfMeasure: product.product_tmpl_id?.uom_id?.name || "kg",
            unitOfMeasureId: product.product_tmpl_id?.uom_id?.id,
            decimalAccuracy,
            unitPrice,
        };
    }

    _setTareIfRequested() {
        if (this.tareRequested) {
            this.tare = this.weight;
            this.tareRequested = false;
        }
    }

    _clearLastWeightIfValid() {
        if (this.lastWeight && this.isWeightValid) {
            this.lastWeight = null;
        }
    }

    requestTare() {
        this.tareRequested = true;
        if (this.isManualMeasurement && !this.loading) {
            this.readWeight();
        } else {
            setTimeout(() => this._setTareIfRequested(), TARE_TIMEOUT_MS);
        }
    }

    get isWeightValid() {
        // LNE requires that the weight changes from the previously
        // added value before another product is allowed to be added.
        return (
            (!this.lastWeight ||
                floatCompare(this.weight, this.lastWeight, {
                    decimals: this.product.decimalAccuracy,
                }) !== 0) &&
            this.netWeight > 0
        );
    }

    get isManualMeasurement() {
        return this._scaleDevice?.manual_measurement;
    }

    get netWeight() {
        return roundPrecision(this.weight - (this.tare || 0), this.product.decimalAccuracy);
    }

    get netWeightString() {
        const weightString = formatFloat(this.netWeight, {
            digits: [0, this.product.decimalAccuracy],
        });
        return `${weightString} ${this.product.unitOfMeasure}`;
    }

    get tareWeightString() {
        const weightString = formatFloat(this.tare || 0, {
            digits: [0, this.product.decimalAccuracy],
        });
        return `${weightString} ${this.product.unitOfMeasure}`;
    }

    get grossWeightString() {
        const weightString = formatFloat(this.weight, {
            digits: [0, this.product.decimalAccuracy],
        });
        return `${weightString} ${this.product.unitOfMeasure}`;
    }

    get unitPriceString() {
        const priceString = this.env.utils.formatCurrency(this.product.unitPrice);
        return `${priceString} / ${this.product.unitOfMeasure}`;
    }

    get totalPriceString() {
        const priceString = this.env.utils.formatCurrency(this.netWeight * this.product.unitPrice);
        return priceString;
    }

    get _scaleDevice() {
        return this.hardwareProxy.deviceControllers.scale;
    }
}

const posScaleService = {
    dependencies: ["hardware_proxy"],
    start(env, deps) {
        return new CertifiedScaleService(env, deps);
    },
};

registry.category("services").add("pos_scale", posScaleService, { force: true });
