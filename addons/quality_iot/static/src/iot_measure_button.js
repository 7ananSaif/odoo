import { _t } from "@web/core/l10n/translation";
import { registry } from '@web/core/registry';
import { onWillUnmount } from "@odoo/owl";
import { IotActionButton } from "./iot_action_button/iot_action_button";

export class IotMeasureWidget extends IotActionButton {
    setup() {
        super.setup();

        this._isMeasuring = true;
        this._keepMeasuring();
        onWillUnmount(() => this._isMeasuring = false);
    }

    _keepMeasuring() {
        if (!this._isMeasuring) {
            return;
        }
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.onMessage(
            iotBoxId,
            deviceIdentifier,
            this.onSuccess.bind(this),
            this.notifyFailure.bind(this)
        );
    }

    async onClick() {
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            { action: 'read_once' },
            this.onSuccess.bind(this),
            this.notifyFailure.bind(this)
        );
        this._isMeasuring = true;
        this._keepMeasuring()
    }

    notifyFailure() {
        this._isMeasuring = false;
        this.notification.add(_t('Could not get measurement from device'), {
            type: 'danger',
        });
    }

    async onSuccess(data) {
        if (!data.value) {
            return this.notifyFailure();
        }
        this._keepMeasuring();
        this.props.record.update({ measure: data.value });
    }
}

registry.category("view_widgets").add("iot_measure", {
    component: IotMeasureWidget,
    extractProps: ({ attrs }) => {
        return { btn_name: attrs.btn_name };
    },
});
