import {
    PosScaleService,
    posScaleService,
} from "@point_of_sale/app/screens/scale_screen/scale_service";
import { patch } from "@web/core/utils/patch";

patch(posScaleService, {
    dependencies: [...posScaleService.dependencies, "iot_http"],
});

patch(PosScaleService.prototype, {
    setup(env, { iot_http }) {
        super.setup(...arguments);
        this.iotHttpService = iot_http;
    },

    get _scaleDevice() {
        return this.hardwareProxy.deviceControllers.scale;
    },

    get isManualMeasurement() {
        return this._scaleDevice?.manual_measurement;
    },

    async _getWeightFromScale() {
        return new Promise((resolve, reject) => {
            const { iotId, identifier } = this._scaleDevice;
            const callback = (data) => {
                try {
                    resolve(this._handleScaleMessage(data));
                } catch (error) {
                    reject(error);
                }
            };

            this.iotHttpService.action(
                iotId,
                identifier,
                { action: "read_once" },
                callback,
                () => {} // avoid timeout notification
            );
        });
    },

    async _readWeightContinuously() {
        const { iotId, identifier } = this._scaleDevice;
        const callback = (data) => {
            try {
                this.weight = this._handleScaleMessage(data);
                this._clearLastWeightIfValid();
                this._setTareIfRequested();
            } catch (error) {
                this.onError?.(error.message);
            }
            if (this.isMeasuring) {
                this.iotHttpService.onMessage(iotId, identifier, callback, callback);
            }
        };
        this.iotHttpService.onMessage(iotId, identifier, callback, () => {});
        // there is not always an event waiting in the iot, so we trigger one
        this.iotHttpService.action(iotId, identifier, { action: "read_once" }, callback, () => {});
    },

    _handleScaleMessage(data) {
        if (data.status.status === "error") {
            throw new Error(`Cannot weigh product - ${data.status.message_body}`);
        } else if (data.status.status === "connected") {
            return data.result || 0;
        }
        // else, do nothing to avoid data.status === "error"
        // corresponding to timeout because weight did not change
        return this.weight;
    },

    _checkScaleIsConnected() {},
});
