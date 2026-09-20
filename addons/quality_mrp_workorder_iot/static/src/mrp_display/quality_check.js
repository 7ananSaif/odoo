import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { QualityCheck } from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";

patch(QualityCheck.prototype, {
    /** override the quality check click behavior to get measurement from an IoT device */
    async clicked() {
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        if (this.type !== "measure" || !iotBoxId || !deviceIdentifier) {
            return super.clicked();
        }
        this.notification.add(_t('Getting measurement...'));
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            { action: "read_once" },
            this.iotUpdateMeasurement.bind(this),
            this._notifyFailure.bind(this)
        );
    },
    async iotUpdateMeasurement(data) {
        if (!data.value) {
            return this.notifyFailure();
        }
        await this.props.record.update({ measure: data.value });
        super.clicked();
    },
})
